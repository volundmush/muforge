import typing
import asyncio
import traceback
import orjson

from dataclasses import dataclass, field

from typing import Dict, Tuple, Optional, Union, List
from collections import defaultdict

from .parser import TelnetCode, TelnetCommand, TelnetData, TelnetNegotiate, TelnetSubNegotiate, parse_telnet
from .options import TelnetOption
from .utils import ensure_crlf
from muforge.apps.portal.capabilities import ClientInfo



class MudTelnetProtocol:

    def __init__(self, supported_options: typing.List[typing.Type[TelnetOption]] = None, text_encoding: str = "utf-8", json_library = None):
        """
        Initialize a MudTelnetProtocol instance.

        Args:
            supported_options (list): A list of TelnetOption classes that the server supports. If this is None, all
                advanced features are disabled. It's recommended to use the ALL_OPTIONS list from the options module.
        """
        self.text_encoding = text_encoding
        self.supported_options = supported_options or list()
        # Various callbacks with different call signatures will be stored here.
        # set them after initializing with telnet.callbacks["name"] = some_async_callable.
        # Raw bytes come in and are appended to the _tn_in_buffer.
        self._tn_in_buffer = bytearray()
        # Private message queue that holds messages like TelnetData, TelnetCommand, TelnetNegotiate, TelnetSubNegotiate.
        # Used by self.output_stream
        self._tn_out_queue = asyncio.Queue()
        # Holds text data sent by client that has yet to have a line ending.
        self._tn_app_data = bytearray()
        self._tn_options: dict[int, TelnetOption] = {}
        # These are currently only used by MCCP2 and MCCP3. They cause byte transformations/encoding/decoding.
        # It's probably not possible to have too many things mucking with bytes in/out. Really, MCCP2 and MCCP3 are
        # terrible enough to deal with as it is.
        self._out_transformers = list()
        self._in_transformers = list()

        # Initialize all provided Telnet Option handlers.
        for op in self.supported_options:
            self._tn_options[op.code] = op(self)

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

        self._tn_in_buffer.extend(data)

        while True:
            # Try to parse a message from the buffer
            consumed, message = parse_telnet(self._tn_in_buffer)
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
        cb = self.callbacks.get("change_capabilities", None)
        for key, value in changes.items():
            setattr(self.capabilities, key, value)
            if cb:
                await cb(key, value)

    async def _tn_at_telnet_message(self, message):
        """
        Responds to data converted from raw data after possible decompression.
        """
        match message:
            case TelnetData():
                await self._tn_handle_data(message)
            case TelnetCommand():
                if not self.capabilities.telnet:
                    await self.change_capabilities({"telnet": True})
                await self._tn_handle_command(message)
            case TelnetNegotiate():
                if not self.capabilities.telnet:
                    await self.change_capabilities({"telnet": True})
                await self._tn_handle_negotiate(message)
            case TelnetSubNegotiate():
                if not self.capabilities.telnet:
                    await self.change_capabilities({"telnet": True})
                await self._tn_handle_subnegotiate(message)

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

            # Call the line callback if it exists
            if cb := self.callbacks.get("line", None):
                await cb(line)

    async def _tn_handle_negotiate(self, message: TelnetNegotiate):
        if op := self._tn_options.get(message.option, None):
            await op.at_receive_negotiate(message)
            return

        # but if we don't have any handler for it...
        match message.command:
            case TelnetCode.WILL:
                msg = TelnetNegotiate(TelnetCode.DONT, message.option)
                await self._tn_out_queue.put(msg)
            case TelnetCode.DO:
                msg = TelnetNegotiate(TelnetCode.WONT, message.option)
                await self._tn_out_queue.put(msg)

    async def _tn_handle_subnegotiate(self, message: TelnetSubNegotiate):
        if op := self._tn_options.get(message.option, None):
            await op.at_receive_subnegotiate(message)

    async def _tn_handle_command(self, message: TelnetCommand):
        if cb := self.callbacks.get("command", None):
            await cb(message.command)

    async def _tn_encode_outgoing_data(self, data: typing.Union[TelnetData, TelnetCommand, TelnetNegotiate, TelnetSubNegotiate]) -> bytes:
        # First we'll convert our object to bytes. It might be a TelnetData, TelnetCommand,
        # TelnetNegotiate, or TelnetSubNegotiate.
        encoded = bytes(data)
        # pass it through any applicable transformations. This is probably only MCCP2.
        for op in self._out_transformers:
            encoded = await op.transform_outgoing_data(encoded)
        # return the encoded data.
        return encoded

    async def output_stream(self) -> typing.AsyncGenerator[bytes, None]:
        """
        This is the main output stream generator. It takes data from the _tn_out_queue,
        encodes it as bytes, and yields it the caller. This is meant to be used in an
        async for loop like so:

        async for data in protocol.output_stream():
            await writer.write(data)

        """
        while data := await self._tn_out_queue.get():
            encoded = await self._tn_encode_outgoing_data(data)
            # certain options need to know when things happen. Primarily MCCP2. So we'll notify them
            # of the data that we now know "has been sent to the client".
            match data:
                case TelnetNegotiate():
                    if op := self._tn_options.get(data.option, None):
                        await op.at_send_negotiate(data)
                case TelnetSubNegotiate():
                    if op := self._tn_options.get(data.option, None):
                        await op.at_send_subnegotiate(data)
            yield encoded

    async def send_line(self, text: str):
        if not text.endswith("\n"):
            text += "\n"
        await self.send_text(text)

    async def send_text(self, text: str):
        converted = ensure_crlf(text)
        await self._tn_out_queue.put(TelnetData(data=converted.encode()))

    async def send_gmcp(self, command: str, data=None):
        if self.capabilities.gmcp:
            op = self._tn_options.get(TelnetCode.GMCP)
            await op.send_gmcp(command, data)

    async def send_mssp(self, data: dict[str, str]):
        if self.capabilities.mssp:
            op = self._tn_options.get(TelnetCode.MSSP)
            await op.send_mssp(data)

    async def send_command(self, data: int):
        await self._tn_out_queue.put(TelnetCommand(command=data))