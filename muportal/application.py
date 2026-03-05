import asyncio
import aiodns
import sys
import traceback

import muforge
from muforge.shared.application import Application as _Application
from muforge.shared.utils import callables_from_module
from loguru import logger


class Application(_Application):
    name = "portal"

    def __init__(self):
        super().__init__()
        self.game_sessions = dict()
        self.resolver = None

        loop = asyncio.get_event_loop()
        if sys.platform != "win32":
            self.resolver = aiodns.DNSResolver(loop=loop)

    async def setup(self):
        await super().setup()

        for k, v in muforge.SETTINGS["PORTAL"]["commands"].items():
            for name, command in callables_from_module(v).items():
                muforge.PORTAL_COMMANDS[command.name] = command
                muforge.PORTAL_COMMANDS_PRIORITY[command.priority].append(command)

    async def handle_new_protocol(self, protocol):
        protocol.core = self
        try:
            self.game_sessions[protocol.session_name] = protocol
            await protocol.run()
        except Exception as err:
            logger.error(traceback.format_exc())
            logger.error(err)
        finally:
            del self.game_sessions[protocol.session_name]
