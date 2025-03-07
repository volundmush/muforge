import asyncio
import asyncpg
from loguru import logger
from mudpy.utils import class_from_module

SETTINGS = dict()
SERVICES = dict()
CLASSES = dict()
SSL_CONTEXT = None
LOCKPARSER = None
LOCKFUNCS = dict()
PGPOOL: asyncpg.Pool = None

APP = None


class Service:
    load_priority: int = 0
    start_priority: int = 0

    def is_valid(self):
        return True

    async def setup(self):
        pass

    async def run(self):
        pass


class Application:
    # name will be either "portal" or "game"
    name: str = None

    def __init__(self):
        self.valid_services: list[Service] = []

    async def setup(self):
        await self.setup_services()

    async def setup_services(self):
        global SERVICES
        for k, v in SETTINGS[self.name.upper()].get("services", dict()).items():
            cls = class_from_module(v)
            srv = cls()
            SERVICES[k] = srv
            if srv.is_valid():
                self.valid_services.append(srv)

        self.valid_services.sort(key=lambda x: x.load_priority)
        for srv in self.valid_services:
            await srv.setup()

    async def run_services(self):
        self.valid_services.sort(key=lambda x: x.start_priority)
        logger.info(f"Starting {self.name} services...")
        async with asyncio.TaskGroup() as tg:
            for srv in self.valid_services:
                tg.create_task(srv.run())

    async def run(self):
        await asyncio.gather(self.start(), self.run_services())

    async def start(self):
        """
        I'm not yet sure what this should do in a running game that's not covered by services,
        but here it is.
        """
        pass
