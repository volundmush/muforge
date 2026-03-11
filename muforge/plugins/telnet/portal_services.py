import asyncio
import uuid

from aiomudtelnet import MudTelnetProtocol
from loguru import logger

import muforge
from muforge.application import Service
from muforge.apps.portal.connections.link import ClientInfo


class TelnetService(Service):
    tls = False
    op_key = "telnet"

    def __init__(self, app, plugin):
        super().__init__(app, plugin)
        self.connections = set()

        config = plugin.settings[self.op_key]

        self.external = config["bind_address"]
        self.port = config["port"]
        self.tls_context = None
        self.server = None
        self.shutdown_event = asyncio.Event()
        self.sessions = set()
        self.telnet_options = list(plugin.telnet_options.values())

    async def setup(self):
        self.server = await asyncio.start_server(
            self.handle_client,
            self.external,
            self.port,
            ssl=self.tls_context,
            backlog=256,
            keep_alive=True,
            ssl_handshake_timeout=10.0 if self.tls_context else None,
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
        logger.info(f"{self.op_key} client connecting from {address}:{port}")
        info = ClientInfo(connection_id=uuid.uuid4())
        info.client_protocol = "telnet"
        info.tls = bool(self.tls_context)
        info.client_address = address

        if self.app.resolver:
            try:
                reverse_lookup = await self.app.resolver.gethostbyaddr(address)
                info.client_hostname = reverse_lookup.aliases
                logger.info(f"{self.op_key} client hostname: {reverse_lookup.name}")
            except Exception:
                pass

        protocol = self.app.classes["mud_telnet_protocol"](
            reader, writer, self, info, supported_options=self.telnet_options
        )

        self.sessions.add(protocol)
        await protocol.run()
        self.sessions.remove(protocol)


class TLSTelnetService(TelnetService):
    tls = True
    op_key = "telnets"

    def __init__(self, app, plugin):
        super().__init__(app, plugin)
        self.tls_context = muforge.SSL_CONTEXT

    def is_valid(self) -> bool:
        return self.tls_context is not None
