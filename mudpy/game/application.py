import mudpy
import importlib
import asyncpg
import orjson
from lark import Lark
from pathlib import Path
from fastapi import FastAPI
from hypercorn import Config
from hypercorn.asyncio import serve
from mudpy import Application as OldApplication
from mudpy.utils import callables_from_module


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
        settings = mudpy.SETTINGS["GAME"]["postgresql"]
        pool = await asyncpg.create_pool(init=init_connection, **settings)
        mudpy.PGPOOL = pool

    async def setup_fastapi(self):
        settings = mudpy.SETTINGS
        shared = settings["SHARED"]
        tls = settings["TLS"]
        networking = settings["GAME"]["networking"]
        self.fastapi_config = Config()
        self.fastapi_config.title = shared["name"]

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
        absolute_phantasm = Path(mudpy.__file__).parent
        grammar = absolute_phantasm / "grammar.lark"
        with open(grammar, "r") as f:
            data = f.read()
            parser = Lark(data)
            mudpy.LOCKPARSER = parser

    async def setup(self):
        await super().setup()
        await self.setup_lark()
        await self.setup_asyncpg()
        await self.setup_fastapi()

        for k, v in mudpy.SETTINGS["GAME"].get("lockfuncs", dict()).items():
            lock_funcs = callables_from_module(v)
            for name, func in lock_funcs.items():
                mudpy.LOCKFUNCS[name] = func

    async def start(self):
        await serve(self.fastapi_instance, self.fastapi_config)
