import asyncio
import ssl
import sys
from pathlib import Path

import aiodns
import semver
from loguru import logger

from .utils.misc import property_from_module


class Service:
    load_priority: int = 0
    start_priority: int = 0

    def __init__(self, app: "BaseApplication", plugin):
        self.app = app
        self.plugin = plugin

    def is_valid(self) -> bool:
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

    def __init__(self, settings):
        self.complete_settings = settings
        self.settings = settings.get(self.name.upper(), dict())
        self.classes: dict[str, type] = dict()
        self.services: dict[str, Service] = dict()
        self.valid_services: list[Service] = []
        self.shutdown_event = asyncio.Event()
        self.task_group = None
        self.plugins: dict[str, "Plugin"] = dict()
        self.plugin_load_order = list()

        self.resolver = None
        self.tls_context = None

        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            self.resolver = aiodns.DNSResolver(loop=loop)

    async def setup_events(self):
        pass

    async def setup_plugins(self):
        for plugin_path in self.complete_settings["MUFORGE"].get("plugins", list()):
            try:
                plugin_class = property_from_module(plugin_path)
            except ImportError as e:
                logger.error(f"Failed to import plugin module {plugin_path}: {e}")
                raise e
            plugin = plugin_class(self)
            self.plugins[plugin.slug()] = plugin

        for k, v in self.plugins.items():
            logger.info(f"Found plugin {k} version {v.version()}.")
            await v.pre_setup()

        remaining = self.plugins.copy()

        while len(remaining):
            to_pop = []
            for slug, plugin in remaining.items():
                dependencies = plugin.depends()
                for check_slug, ver in dependencies:
                    if found := self.plugins.get(check_slug, None):
                        if not semver.match(found.version(), ver):
                            logger.error(
                                f"Plugin {slug} depends on plugin {check_slug} with version {ver}, but found version {found.version()}."
                            )
                            raise Exception(
                                f"Plugin {slug} depends on plugin {check_slug} with version {ver}, but found version {found.version()}."
                            )
                    else:
                        logger.error(
                            f"Plugin {slug} depends on missing plugin {check_slug}."
                        )
                        raise Exception(
                            f"Plugin {slug} depends on missing plugin {check_slug}."
                        )
                self.plugin_load_order.append(plugin)
                to_pop.append(slug)
                logger.info(
                    f"Resolved dependencies for plugin {slug} version {plugin.version()}."
                )
            for slug in to_pop:
                remaining.pop(slug)

        for k, v in self.plugins.items():
            await v.post_setup()

    async def setup_tls(self):
        cert = self.complete_settings.get("TLS", dict()).get("certificate", None)
        key = self.complete_settings.get("TLS", dict()).get("key", None)
        if cert and key and Path(cert).exists() and Path(key).exists():
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(cert, key)
            self.tls_context = context
            logger.info("TLS context configured from certificate and key files.")
        else:
            logger.warning("TLS certificate or key not found, TLS is not available.")

    async def setup(self):
        await self.setup_tls()
        await self.setup_plugins()
        await self.setup_classes()
        await self.setup_events()
        await self.setup_services()

    async def setup_classes(self):
        temp_classes = dict()
        for p in self.plugin_load_order:
            if classes := getattr(p, f"{self.name}_classes")():
                for k, v in classes.items():
                    temp_classes[k] = (p, v)

        for k, (p, cls) in temp_classes.items():
            self.classes[k] = cls

    async def setup_services(self):
        temp_services = dict()
        for p in self.plugin_load_order:
            if services := getattr(p, f"{self.name}_services")():
                for k, v in services.items():
                    temp_services[k] = (p, v)

        for k, (p, srv_class) in temp_services.items():
            srv = srv_class(self, p)
            if srv.is_valid():
                logger.info(f"Setting up service: {k}")
                self.services[k] = srv
            else:
                logger.warning(f"Invalid service: {k}, will not be loaded")

        valid_services = list(self.services.values())
        valid_services.sort(key=lambda x: x.load_priority)
        logger.info(f"Setting up {len(valid_services)} services...")
        for srv in valid_services:
            await srv.setup()
        logger.info("Services setup complete.")

    async def run(self):
        services = list(self.services.values())
        services.sort(key=lambda x: x.start_priority)
        logger.info("Starting services...")
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            for srv in services:
                logger.info(f"Starting service: {srv.__class__.__name__}")
                tg.create_task(srv.run())
            tg.create_task(self.start())

            await self.shutdown_event.wait()
            raise asyncio.CancelledError()

        logger.info("All services have stopped.")

    async def start(self):
        pass

    def shutdown(self):
        self.shutdown_event.set()

    def exception_handler(self, loop, context):
        exception = context.get("exception")
        if isinstance(exception, KeyboardInterrupt):
            print("Going down...")
            self.shutdown()
