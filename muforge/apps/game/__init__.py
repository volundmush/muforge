import asyncio
from pathlib import Path

from hypercorn import Config
from hypercorn.asyncio import serve
from loguru import logger

import muforge
from muforge.application import BaseApplication
from muforge.utils.misc import callables_from_module, property_from_module

from .fastapi import assemble_fastapi


class Application(BaseApplication):
    name = "game"

    def __init__(self, settings):
        super().__init__(settings)
        self.fastapi_config = None
        self.fastapi_instance = None

    async def setup_fastapi(self):
        settings = self.settings["webserver"]
        self.fastapi_config = Config()
        self.fastapi_config.title = self.complete_settings["MUFORGE"]["name"]

        external = settings["bind_address"]
        bind_to = f"{external}:{settings['port']}"
        self.fastapi_config.bind = [bind_to]
        self.fastapi_config._quic_bind = [bind_to]

        if settings.get("tls", False):
            tls = self.complete_settings["TLS"]
            if Path(tls["certificate"]).exists():
                self.fastapi_config.certfile = str(Path(tls["certificate"]).absolute())
            if Path(tls["key"]).exists():
                self.fastapi_config.keyfile = str(Path(tls["key"]).absolute())

        self.fastapi_instance = await assemble_fastapi(self, self.fastapi_config)

    async def setup(self):
        await super().setup()
        await self.setup_fastapi()
        await self.setup_plugins_final()

    async def setup_plugins_final(self):
        for p in self.plugin_load_order:
            if hasattr(p, "setup_final"):
                await p.setup_final()

    async def setup_listeners(self):
        for k, v in muforge.SETTINGS["GAME"].get("listeners", dict()).items():
            listener_class = property_from_module(v)
            listener = listener_class()
            muforge.LISTENERS[k] = listener
            for table in listener.tables:
                muforge.LISTENERS_TABLE[table].append(listener)

    async def handle_postgre_notification(self, conn, pid, channel, payload):
        decoded = orjson.loads(payload)
        args = [decoded["table"], decoded["id"]]

        if not (listeners := muforge.LISTENERS_TABLE.get(decoded["table"], [])):
            return

        match decoded["operation"]:
            case "UPDATE":
                for listener in listeners:
                    await listener.on_update(*args)
            case "INSERT":
                for listener in listeners:
                    await listener.on_insert(*args)
            case "DELETE":
                for listener in listeners:
                    await listener.on_delete(*args)

    async def postgre_listener(self):
        async with self.db.connection() as conn:
            await conn.add_listener("table_changes", self.handle_postgre_notification)
            while True:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break

    async def start(self):
        self.task_group.create_task(serve(self.fastapi_instance, self.fastapi_config))
        self.task_group.create_task(self.postgre_listener())
