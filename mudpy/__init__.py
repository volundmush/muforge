import asyncio
import os
import ssl
from pathlib import Path
from loguru import logger
from mudpy.utils import class_from_module

SETTINGS = dict()
SERVICES = dict()
CLASSES = dict()

APP = None


class Service:
    load_priority: int = 0
    start_priority: int = 0

    def __init__(self, core):
        self.core = core

    def is_valid(self):
        return True

    async def setup(self):
        pass

    async def run(self):
        pass


class Application:
    # name will be either "portal" or "game"
    name: str = None

    def __init__(self, settings: dict):
        global SETTINGS, APP
        APP = self
        SETTINGS.update(settings)
        self.valid_services: list[Service] = []
        self.cert = SETTINGS["TLS"].get("certificate", None)
        self.key = SETTINGS["TLS"].get("key", None)
        self.ssl_context = None
        if (
            self.cert
            and self.key
            and Path(self.cert).exists()
            and Path(self.key).exists()
        ):
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(self.cert, self.key)

    async def setup(self):
        await self.setup_services()

    async def setup_services(self):
        global SERVICES
        for k, v in SETTINGS[self.name.upper()]["services"].items():
            cls = class_from_module(v)
            srv = cls(self)
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
