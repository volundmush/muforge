import asyncio
import asyncpg
from loguru import logger
from mudforge.utils import class_from_module, Broadcaster
from collections import defaultdict

SETTINGS = dict()
SERVICES = dict()
CLASSES = dict()
SSL_CONTEXT = None
LOCKPARSER = None
LOCKFUNCS = dict()
LOCK_CACHE = dict()
PGPOOL: asyncpg.Pool = None
LISTENERS = dict()
LISTENERS_TABLE = defaultdict(list)
BROADCASTERS: dict[str, Broadcaster] = defaultdict(Broadcaster)

COMMANDS: dict[str, "Command"] = dict()

COMMANDS_PRIORITY: dict[int, list["Command"]] = defaultdict(list)

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

    def shutdown(self):
        pass


class Application:
    # name will be either "portal" or "game"
    name: str = None

    def __init__(self):
        self.valid_services: list[Service] = []
        self.shutdown_event = asyncio.Event()
        self.task_group = None

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
