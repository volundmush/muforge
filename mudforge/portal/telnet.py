import asyncio
import orjson
from loguru import logger
import traceback
from datetime import datetime

import mudforge
from mudforge.utils import generate_name
from mudforge import Service

from aiomudtelnet import MudTelnetProtocol
from aiomudtelnet.options import ALL_OPTIONS
from aiomudtelnet.parser import TelnetCode

from .base_connection import BaseConnection, ClientCommand


class TelnetConnection(BaseConnection):

    def __repr__(self):
        return f"<TelnetConnection: {self.session_name}>"

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server
    ):
        super().__init__()
        self.telnet = MudTelnetProtocol(
            capabilities=self.capabilities,
            supported_options=ALL_OPTIONS,
            logger=logger,
            json_library=orjson,
        )
        self._tn_reader = reader
        self._tn_writer = writer
        self._tn_server = server
        self.telnet.callbacks["line"] = self.at_receive_line
        self.telnet.callbacks["gmcp"] = self.at_receive_gmcp
        self.telnet.callbacks["change_capabilities"] = self.at_capability_change

    async def setup(self):
        for task in (
            self._tn_run_reader,
            self._tn_run_writer,
            self._tn_run_negotiation,
        ):
            self.task_group.create_task(task())

    async def _tn_run_reader(self):
        while True:
            try:
                data = await self._tn_reader.read(1024)
                if not data:
                    self.shutdown_cause = "reader_eof"
                    self.shutdown_event.set()
                    return
                self.last_active_at = datetime.now()
                await self.telnet.receive_data(data)
            except asyncio.CancelledError:
                return
            except ConnectionResetError as e:
                self.shutdown_cause = "reader_reset"
                self.shutdown_event.set()
                return
            except Exception as err:
                logger.error(traceback.format_exc())
                logger.error(err)
                self.shutdown_cause = "reader_unknown_error"
                self.shutdown_event.set()
                return

    async def _tn_run_writer(self):
        try:
            async for data in self.telnet.output_stream():
                self._tn_writer.write(data)
                await self._tn_writer.drain()
        except asyncio.CancelledError:
            # Optionally, perform any cleanup before re-raising.
            # For example, if you need to close the writer:
            try:
                self._tn_writer.close()
                await self._tn_writer.wait_closed()
            except Exception:
                pass
        except Exception as err:
            logger.error(traceback.format_exc())
            logger.error(err)

    async def _tn_run_negotiation(self):
        try:
            await self.telnet.start()
            if self.capabilities.telnet:
                self.task_group.create_task(self.run_keepalive())
            await self.run_link()
        except Exception as err:
            logger.error(traceback.format_exc())
            logger.error(err)
        except asyncio.CancelledError:
            return

    async def send_text(self, text: str):
        await self.telnet.send_text(text)

    async def send_gmcp(self, command: str, data=None):
        await self.telnet.send_gmcp(command, data)

    async def send_mssp(self, data: dict[str, str]):
        await self.telnet.send_mssp(data)

    async def run_keepalive(self):
        try:
            await self.telnet.send_command(TelnetCode.NOP)
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return


class TelnetService(Service):
    tls = False
    op_key = "telnet"

    def __init__(self):
        self.connections = set()

        self.external = mudforge.SETTINGS["SHARED"]["external"]
        self.port = mudforge.SETTINGS["PORTAL"]["networking"][self.op_key]
        self.tls_context = None
        self.server = None
        self.shutdown_event = asyncio.Event()
        self.sessions = set()

    async def setup(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.external, self.port, ssl=self.tls_context
        )
        # Log or print that the server has started
        logger.info(f"{self.op_key} server created on {self.external}:{self.port}")

    async def run(self):
        logger.info(f"{self.op_key} server started on {self.external}:{self.port}")
        try:
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info(f"{self.op_key} server cancellation received.")
            for session in self.sessions.copy():
                session.shutdown_cause = "graceful_shutdown"
                session.shutdown_event.set()
        finally:
            # Make sure to close the server if not already closed.
            self.server.close()
            await self.server.wait_closed()

    def shutdown(self):
        self.shutdown_event.set()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        address, port = writer.get_extra_info("peername")
        protocol = mudforge.CLASSES["telnet_connection"](reader, writer, self)
        protocol.session_name = generate_name(
            self.op_key, mudforge.APP.game_sessions.keys()
        )
        protocol.host_address = address
        protocol.host_port = port
        if mudforge.APP.resolver:
            reverse = await mudforge.APP.resolver.gethostbyaddr(address)
            protocol.host_names = reverse.aliases
        self.sessions.add(protocol)
        await mudforge.APP.handle_new_protocol(protocol)
        self.sessions.remove(protocol)


class TLSTelnetService(TelnetService):
    tls = True
    op_key = "telnets"

    def __init__(self):
        super().__init__()
        self.tls_context = mudforge.SSL_CONTEXT

    def is_valid(self):
        return self.tls_context is not None
