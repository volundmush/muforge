import asyncio
from loguru import logger

from .service import Service
from .utils import callables_from_module, property_from_module

import muforge

class Application:
    # name will be either "portal" or "game"
    name: str = None

    def __init__(self):
        self.valid_services: list[Service] = []
        self.shutdown_event = asyncio.Event()
        self.task_group = None

    async def setup_events(self):
        for k, v in muforge.SETTINGS.get("EVENTS", dict()).items():
            for name, cls in callables_from_module(v).items():
                muforge.EVENTS[name] = cls

    async def setup(self):
        await self.setup_events()
        await self.setup_services()

    async def setup_services(self):
        for k, v in muforge.SETTINGS[self.name.upper()].get("services", dict()).items():
            cls = property_from_module(v)
            srv = cls()
            muforge.SERVICES[k] = srv
            if srv.is_valid():
                self.valid_services.append(srv)

        self.valid_services.sort(key=lambda x: x.load_priority)
        for srv in self.valid_services:
            await srv.setup()

    async def run(self):
        self.valid_services.sort(key=lambda x: x.start_priority)
        logger.info("Starting services...")
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            for srv in self.valid_services:
                tg.create_task(srv.run())
            await self.start()

            await self.shutdown_event.wait()
            raise asyncio.CancelledError()

        logger.info("All services have stopped.")

    def shutdown(self):
        self.shutdown_event.set()

    def exception_handler(self, loop, context):
        exception = context.get("exception")
        if isinstance(exception, KeyboardInterrupt):
            print("Going down...")
            self.shutdown()

    async def start(self):
        """
        I'm not yet sure what this should do in a running game that's not covered by services,
        but here it is.
        """
        pass