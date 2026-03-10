import asyncio
import sys
import aiodns
from loguru import logger
import importlib
import semver

import muforge
from .utils.misc import callables_from_module, property_from_module

class Service:
    load_priority: int = 0
    start_priority: int = 0

    def __init__(self, app: "BaseApplication"):
        self.app = app

    def is_valid(self):
        return True

    async def setup(self):
        pass

    async def run(self):
        pass

    def shutdown(self):
        pass

class BaseApplication:
    # name will be either "portal" or "game"
    name: str = None

    def __init__(self):
        self.valid_services: list[Service] = []
        self.shutdown_event = asyncio.Event()
        self.task_group = None
        self.plugin_load_order = list()

        self.resolver = None

        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            self.resolver = aiodns.DNSResolver(loop=loop)

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
        
        for k, v in muforge.PLUGINS.items():
            logger.info(f"Found plugin {k} version {v.version()}.")
            await v.pre_setup()

        remaining = muforge.PLUGINS.copy()
        
        while len(remaining) > len(self.plugin_load_order):
            to_pop = []
            for slug, plugin in muforge.PLUGINS.items():
                dependencies = plugin.depends()
                for (check_slug, ver) in dependencies:
                    if found := muforge.PLUGINS.get(check_slug, None):
                        if not semver.match(found.version(), ver):
                            logger.error(f"Plugin {slug} depends on plugin {check_slug} with version {ver}, but found version {found.version()}.")
                            raise Exception(f"Plugin {slug} depends on plugin {check_slug} with version {ver}, but found version {found.version()}.")
                    else:
                        logger.error(f"Plugin {slug} depends on missing plugin {check_slug}.")
                        raise Exception(f"Plugin {slug} depends on missing plugin {check_slug}.")
                self.plugin_load_order.append(plugin)
                to_pop.append(slug)
                logger.info(f"Resolved dependencies for plugin {slug} version {plugin.version()}.")
            for slug in to_pop:
                remaining.pop(slug)
        
        for k, v in muforge.PLUGINS.items():
            await v.post_setup()
    
    async def setup(self):
        await self.setup_plugins()
        await self.setup_events()
        await self.setup_services()

    async def setup_services(self):
        for k, v in muforge.SETTINGS[self.name.upper()].get("services", dict()).items():
            cls = property_from_module(v)
            srv = cls(self)
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