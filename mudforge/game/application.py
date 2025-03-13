import mudforge
import importlib
import asyncpg
import orjson
import asyncio
from loguru import logger
from lark import Lark
from pathlib import Path
from fastapi import FastAPI
from hypercorn import Config
from hypercorn.asyncio import serve
from mudforge import Application as OldApplication
from mudforge.utils import callables_from_module, class_from_module, EventHub


def decode_json(data: bytes):
    decoded = orjson.loads(data)
    return decoded


async def init_connection(conn: asyncpg.Connection):
    await conn.set_type_codec(
        "jsonb",  # The PostgreSQL type to target.
        encoder=lambda v: orjson.dumps(v).decode("utf-8"),
        decoder=decode_json,
        schema="pg_catalog",
        format="text",
    )


class Application(OldApplication):
    name = "game"

    def __init__(self):
        super().__init__()
        self.fastapi_config = None
        self.fastapi_instance = None

    async def setup_asyncpg(self):
        settings = mudforge.SETTINGS["POSTGRESQL"]
        pool = await asyncpg.create_pool(init=init_connection, **settings)
        mudforge.PGPOOL = pool

    async def setup_fastapi(self):
        settings = mudforge.SETTINGS
        shared = settings["SHARED"]
        tls = settings["TLS"]
        networking = settings["GAME"]["networking"]
        self.fastapi_config = Config()
        self.fastapi_config.title = settings["MSSP"]["NAME"]

        external = shared["external"]
        bind_to = f"{external}:{networking['port']}"
        self.fastapi_config.bind = [bind_to]

        if Path(tls["certificate"]).exists():
            self.fastapi_config.certfile = tls["certificate"]
        if Path(tls["key"]).exists():
            self.fastapi_config.keyfile = tls["key"]

        self.fastapi_instance = FastAPI()
        routers = settings["FASTAPI"]["routers"]
        for k, v in routers.items():
            v = importlib.import_module(v)
            self.fastapi_instance.include_router(v.router, prefix=f"/{k}", tags=[k])

    async def setup_lark(self):
        absolute_phantasm = Path(mudforge.__file__).parent
        grammar = absolute_phantasm / "grammar.lark"
        with open(grammar, "r") as f:
            data = f.read()
            parser = Lark(data)
            mudforge.LOCKPARSER = parser

    async def setup(self):
        await super().setup()
        mudforge.EVENT_HUB = EventHub()
        await self.setup_lark()
        await self.setup_asyncpg()
        await self.setup_fastapi()

        for k, v in mudforge.SETTINGS["GAME"].get("lockfuncs", dict()).items():
            lock_funcs = callables_from_module(v)
            for name, func in lock_funcs.items():
                mudforge.LOCKFUNCS[name] = func

        for k, v in mudforge.SETTINGS["GAME"].get("listeners", dict()).items():
            listener_class = class_from_module(v)
            listener = listener_class()
            mudforge.LISTENERS[k] = listener
            for table in listener.tables:
                mudforge.LISTENERS_TABLE[table].append(listener)

    async def handle_postgre_notification(self, conn, pid, channel, payload):
        decoded = orjson.loads(payload)
        args = [decoded["table"], decoded["id"]]

        if not (listeners := mudforge.LISTENERS_TABLE.get(decoded["table"], [])):
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
        async with mudforge.PGPOOL.acquire() as conn:
            await conn.add_listener("table_changes", self.handle_postgre_notification)
            while True:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break

    async def system_pinger(self):
        from mudforge.events.system import SystemPing

        try:
            while True:
                await mudforge.EVENT_HUB.broadcast(SystemPing())
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            return

    async def start(self):
        self.task_group.create_task(serve(self.fastapi_instance, self.fastapi_config))
        self.task_group.create_task(self.postgre_listener())
        self.task_group.create_task(self.system_pinger())
