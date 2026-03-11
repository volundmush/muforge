import asyncio
import typing
import uuid
from dataclasses import dataclass

from loguru import logger
from rich.color import ColorType

from muforge.apps.portal.connections.link import (
    ClientInfo,
    ConnectionLink,
    LinkData,
    LinkDisconnect,
    LinkUpdate,
)

from .options import TelnetOption
from .parser import (
    ProtocolError,
    TelnetCode,
    TelnetCommand,
    TelnetData,
    TelnetNegotiate,
    TelnetSubNegotiate,
    parse_telnet,
)
from .utils import ensure_crlf


class MSSPRequest:
    async def custom_handler(self, conn: "BaseConnection"):
        live_mssp = await conn.api_call("GET", "/system/mssp")


class MudTelnetProtocol:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        service,
        info: ClientInfo,
        supported_options: typing.List[typing.Type[TelnetOption]] = None,
        text_encoding: str = "utf-8",
        json_library=None,
    ):
        """
        Initialize a MudTelnetProtocol instance.

        Args:
            supported_options (list): A list of TelnetOption classes that the server supports. If this is None, all
                advanced features are disabled. It's recommended to use the ALL_OPTIONS list from the options module.
        """
        self.reader = reader
        self.writer = writer
        self.service = service
        self.link = ConnectionLink(info)
        self.text_encoding = text_encoding
        self.supported_options = supported_options or list()
        # Various callbacks with different call signatures will be stored here.
        # set them after initializing with telnet.callbacks["name"] = some_async_callable.
        # Raw bytes come in and are appended to the _tn_in_buffer.
        self._tn_in_buffer = bytearray()
        # Private message queue that holds messages like TelnetData, TelnetCommand, TelnetNegotiate, TelnetSubNegotiate.
        # Used by self.output_stream
        self._tn_out_queue: asyncio.Queue[typing.Optional[bytes]] = asyncio.Queue()
        # Holds text data sent by client that has yet to have a line ending.
        self._tn_app_data = bytearray()
        self._tn_options: dict[int, TelnetOption] = {}
        # These are currently only used by MCCP2 and MCCP3. They cause byte transformations/encoding/decoding.
        # It's probably not possible to have too many things mucking with bytes in/out. Really, MCCP2 and MCCP3 are
        # terrible enough to deal with as it is.
        self._out_transformers = list()
        self._in_transformers = list()
        self.shutdown_event = asyncio.Event()
        self.shutdown_reason = None
        self.linked = False
        self._link_disconnect_sent = False
        self._shutdown_lock = asyncio.Lock()
        self.uses_telnet = False

        match self.plugin.settings.get("color_mode", 1):
            case 0:
                self.link.info.color = ColorType.DEFAULT
            case 1:
                self.link.info.color = ColorType.STANDARD
            case 2:
                self.link.info.color = ColorType.EIGHT_BIT
            case 3:
                self.link.info.color = ColorType.TRUECOLOR
            case _:
                self.link.info.color = ColorType.DEFAULT

        # Initialize all provided Telnet Option handlers.
        for op in self.supported_options:
            self._tn_options[op.code] = op(self)

    @property
    def plugin(self):
        return self.service.plugin

    async def shutdown(self, reason: str, *, notify_link: bool = True):
        async with self._shutdown_lock:
            if self.shutdown_event.is_set():
                return

            self.shutdown_reason = self.shutdown_reason or reason

            if notify_link and self.linked and not self._link_disconnect_sent:
                await self.link.incoming_queue.put(
                    LinkDisconnect(reason=self.shutdown_reason)
                )
                self._link_disconnect_sent = True

            self.shutdown_event.set()
            await self._tn_out_queue.put(None)

    async def _run_socket_reader(self):
        chunk_size = 65536

        try:
            while True:
                data = await self.reader.read(chunk_size)
                if not data:
                    await self.shutdown("client_disconnect")
                    return
                await self.receive_data(data)
        except asyncio.CancelledError:
            raise
        except asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError:
            await self.shutdown("connection_lost")
        finally:
            self.shutdown_event.set()

    async def _run_socket_writer(self):
        """
        The _tn_out_queue just contains bytes objects to be written.
        All encoding is done in _tn_enqueue_outgoing_data.
        """
        try:
            while True:
                data = await self._tn_out_queue.get()
                if data is None:
                    break
                self.writer.write(data)
                await self.writer.drain()
        except asyncio.CancelledError:
            raise
        except ConnectionResetError, BrokenPipeError:
            await self.shutdown("connection_lost")
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def handle_outgoing_link_data(self, package: str, data):
        match package:
            case "Text.ANSI" | "Text" | "Text.Plain":
                await self.send_text(data)
            case _:
                await self.send_gmcp(package, data)

    async def _run_connection(self):
        self.linked = True

        app = self.plugin.app
        service = app.services["connection"]
        await service.pending_links.put(self.link)

        while msg := await self.link.outgoing_queue.get():
            match msg:
                case LinkData(package=package, data=data):
                    await self.handle_outgoing_link_data(package, data)
                case LinkDisconnect(reason=reason):
                    await self.shutdown(reason, notify_link=False)
                    return
                case LinkUpdate():
                    pass

    async def _run_keepalive(self):
        pass

    async def run(self):
        async with asyncio.TaskGroup() as tg:
            reader_task = tg.create_task(self._run_socket_reader())
            writer_task = tg.create_task(self._run_socket_writer())
            start_task = tg.create_task(self.start())
            keepalive_task = tg.create_task(self._run_keepalive())

            await self.shutdown_event.wait()

            if not reader_task.done():
                reader_task.cancel()
            if not start_task.done():
                start_task.cancel()
            if not keepalive_task.done():
                keepalive_task.cancel()
            if not writer_task.done():
                await self._tn_out_queue.put(None)

    async def start(self, timeout: float = 0.5):
        """
        Fires off the initial barrage of negotiations and prepares events that signify end of negotiations.

        Will wait for <timeout> to complete.
        """
        for code, op in self._tn_options.items():
            await op.start()

        ops = [op.negotiation.wait() for op in self._tn_options.values()]

        try:
            await asyncio.wait_for(asyncio.gather(*ops), timeout)
        except asyncio.TimeoutError as err:
            pass

        if self.shutdown_event.is_set():
            return

        if not self.uses_telnet and self.plugin.settings.get("warn_no_telnet", True):
            recommended = self.plugin.settings.get("recommended_clients", [])
            await self.send_line(
                "Warning: Your client does not support Telnet negotiation."
            )
            if recommended:
                await self.send_line(
                    f"Consider using a MU* client, such as {', '.join(recommended)}."
                )

        await self._run_connection()

    async def receive_data(self, data: bytes) -> int:
        """
        This is the main entry point for incoming data.
        It will process at most one TelnetMessage from the incoming data.
        Extra bytes are held onto in the _tn_in_buffer until they can be processed.

        It returns the size of the in_buffer in bytes after processing.
        This is useful for determining if the buffer is growing or shrinking too much.
        """
        # Route all bytes through the incoming transformers. This is
        # probably only MCCP3.
        in_data = data
        for op in self._in_transformers:
            in_data = await op.transform_incoming_data(in_data)

        self._tn_in_buffer.extend(in_data)

        app_buffer_size = self.plugin.settings.get("application_buffer_size", 16384)
        sub_buffer_size = self.plugin.settings.get("subnegotiate_buffer_size", 4096)

        while True:
            # Try to parse a message from the buffer
            try:
                consumed, message = parse_telnet(
                    self._tn_in_buffer, app_buffer_size, sub_buffer_size
                )
            except ProtocolError as e:
                logger.warning(f"{self}: Protocol error: {e}")
                await self.shutdown(f"protocol_error: {e}")
                return len(self._tn_in_buffer)
            if message is None:
                break
            # advance the buffer by the number of bytes consumed
            self._tn_in_buffer = self._tn_in_buffer[consumed:]
            # Do something with the message.
            # If MCCP3 engages it will actually decompress self._tn_in_buffer in-place
            # so it's safe to keep iterating.
            await self._tn_at_telnet_message(message)

        return len(self._tn_in_buffer)

    async def change_capabilities(self, changes: dict[str, typing.Any]):
        for k, v in changes.items():
            match k:
                case "color":
                    self.link.info.color = v
                case "encoding":
                    self.link.info.encoding = v
                case "height":
                    self.link.info.height = v
                case "width":
                    self.link.info.width = v
                case "screen_reader":
                    self.link.info.screen_reader = v
                case _:
                    pass
        if self.linked:
            await self.link.incoming_queue.put(LinkUpdate(changes))

    async def _tn_at_telnet_message(self, message):
        """
        Responds to data converted from raw data after possible decompression.
        """
        match message:
            case TelnetData():
                await self._tn_handle_data(message)
            case TelnetCommand():
                self.uses_telnet = True
                await self._tn_handle_command(message)
            case TelnetNegotiate():
                self.uses_telnet = True
                await self._tn_handle_negotiate(message)
            case TelnetSubNegotiate():
                self.uses_telnet = True
                await self._tn_handle_subnegotiate(message)

    async def _tn_handle_command(self, message: TelnetCommand):
        pass

    async def _tn_handle_data(self, message: TelnetData):
        self._tn_app_data.extend(message.data)

        # scan self._app_data for lines ending in \r\n...
        while True:
            # Find the position of the next newline character
            newline_pos = self._tn_app_data.find(b"\n")
            if newline_pos == -1:
                break  # No more newlines

            # Extract the line, trimming \r\n at the end
            line = (
                self._tn_app_data[:newline_pos]
                .rstrip(b"\r\n")
                .decode(self.text_encoding, errors="ignore")
            )

            # Remove the processed line from _app_data
            self._tn_app_data = self._tn_app_data[newline_pos + 1 :]

            await self.link.incoming_queue.put(LinkData("Text.Command", line))

    async def _tn_handle_negotiate(self, message: TelnetNegotiate):
        if op := self._tn_options.get(message.option, None):
            await op.at_receive_negotiate(message)
            return

        # but if we don't have any handler for it...
        match message.command:
            case TelnetCode.WILL:
                msg = TelnetNegotiate(TelnetCode.DONT, message.option)
                await self._tn_enqueue_outgoing_data(msg)
            case TelnetCode.DO:
                msg = TelnetNegotiate(TelnetCode.WONT, message.option)
                await self._tn_enqueue_outgoing_data(msg)

    async def _tn_handle_subnegotiate(self, message: TelnetSubNegotiate):
        if op := self._tn_options.get(message.option, None):
            await op.at_receive_subnegotiate(message)

    async def _tn_enqueue_outgoing_data(
        self,
        data: typing.Union[
            TelnetData, TelnetCommand, TelnetNegotiate, TelnetSubNegotiate
        ],
    ):
        # First we'll convert our object to bytes. It might be a TelnetData, TelnetCommand,
        # TelnetNegotiate, or TelnetSubNegotiate.
        encoded = bytes(data)
        # pass it through any applicable transformations. This is probably only MCCP2.
        for op in self._out_transformers:
            encoded = await op.transform_outgoing_data(encoded)
        # return the encoded data.
        await self._tn_out_queue.put(encoded)

    async def send_line(self, text: str):
        if not text.endswith("\n"):
            text += "\n"
        await self.send_text(text)

    async def send_text(self, text: str):
        converted = ensure_crlf(text)
        await self._tn_enqueue_outgoing_data(TelnetData(data=converted.encode()))

    async def send_gmcp(self, package: str, data=None):
        if op := self._tn_options.get(TelnetCode.GMCP):
            if op.status.local.enabled or op.status.remote.enabled:
                await op.send_gmcp(package, data)

    async def send_mssp(self, data: dict[str, str]):
        if op := self._tn_options.get(TelnetCode.MSSP):
            if op.status.local.enabled or op.status.remote.enabled:
                await op.send_mssp(data)

    async def send_command(self, data: int):
        await self._tn_enqueue_outgoing_data(TelnetCommand(command=data))
