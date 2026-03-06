import asyncio
from loguru import logger
import importlib
import semver

import muforge
from .utils.misc import callables_from_module, property_from_module

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
        self.plugin_load_order = list()

    async def setup_events(self):
        for k, v in muforge.SETTINGS.get("EVENTS", dict()).items():
            for name, cls in callables_from_module(v).items():
                muforge.EVENTS[name] = cls

    async def setup_plugins(self):
        for plugin_path in muforge.PLUGIN_PATHS:
            try:
                plugin_module = importlib.import_module(plugin_path)
            except ImportError as e:
                logger.error(f"Failed to import plugin module {plugin_path}: {e}")
                raise e
            try:
                plugin_class = property_from_module(plugin_module.plugin)
            except AttributeError as e:
                logger.error(f"Plugin module {plugin_path} does not have a 'plugin' attribute: {e}")
                raise e
            plugin = plugin_class(self)
            muforge.PLUGINS[plugin.slug()] = plugin

    async def setup(self):
        await self.setup_plugins()
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