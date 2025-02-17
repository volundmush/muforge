import asyncio
import aiodns
import sys
import traceback

from mudpy import Application as _Application
from loguru import logger

class Application(_Application):
    name = "portal"

    def __init__(self, settings):
        super().__init__(settings)
        self.game_sessions = dict()
        self.resolver = None

        loop = asyncio.get_event_loop()
        if sys.platform != 'win32':
            self.resolver = aiodns.DNSResolver(loop=loop)

    async def handle_new_protocol(self, protocol):
        protocol.core = self
        try:
            self.game_sessions[protocol.capabilities.session_name] = protocol
            await protocol.run()
        except Exception as err:
            logger.error(traceback.format_exc())
            logger.error(err)
        finally:
            del self.game_sessions[protocol.capabilities.session_name]