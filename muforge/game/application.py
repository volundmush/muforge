import muforge
import importlib
import asyncpg
import orjson
import asyncio
import tomllib

from lark import Lark
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from hypercorn import Config
from hypercorn.asyncio import serve

from muforge.shared.application import Application as OldApplication
from muforge.shared.utils import callables_from_module, property_from_module
from muforge.game.systems.events import EventHub

async def init_connection(conn: asyncpg.Connection):
    await conn.set_type_codec(
        "jsonb",  # The PostgreSQL type to target.
        encoder=lambda v: orjson.dumps(v).decode("utf-8"),
        decoder=lambda data: orjson.loads(data),
        schema="pg_catalog",
        format="text",
    )


class Application(OldApplication):
    name = "game"

    def __init__(self):
        super().__init__()
        self.fastapi_config = None
        self.fastapi_instance = None

    async def setup_commands(self):
        for k, v in muforge.SETTINGS["GAME"]["commands"].items():
            for name, command in callables_from_module(v).items():
                muforge.GAME_COMMANDS[command.name] = command
                muforge.GAME_COMMANDS_PRIORITY[command.priority].append(command)

    async def setup_asyncpg(self):
        settings = muforge.SETTINGS["POSTGRESQL"]
        pool = await asyncpg.create_pool(init=init_connection, **settings)
        muforge.PGPOOL = pool

    async def setup_fastapi(self):
        settings = muforge.SETTINGS
        shared = settings["SHARED"]
        tls = settings["TLS"]
        networking = settings["GAME"]["networking"]
        self.fastapi_config = Config()
        self.fastapi_config.title = settings["MSSP"]["NAME"]

        external = shared["external"]
        bind_to = f"{external}:{networking['port']}"
        self.fastapi_config.bind = [bind_to]
        self.fastapi_config._quic_bind = [bind_to]

        if Path(tls["certificate"]).exists():
            self.fastapi_config.certfile = str(Path(tls["certificate"]).absolute())
        if Path(tls["key"]).exists():
            self.fastapi_config.keyfile = str(Path(tls["key"]).absolute())

        self.fastapi_instance = FastAPI()
        app = self.fastapi_instance

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        static_dir = Path() / "static"
        app.mount("/static", StaticFiles(directory="static"), name="static")

        def render_index() -> HTMLResponse:
            index_path = static_dir / "index.html"
            if not index_path.exists():
                return HTMLResponse(
                    "<h1>Muforge Web UI</h1><p>Put index.html in mutemplate/static/</p>",
                    status_code=404,
                )
            return HTMLResponse(index_path.read_text(encoding="utf-8"))

        @app.get("/", response_class=HTMLResponse)
        async def root():
            return render_index()


        @app.get("/index.html", response_class=HTMLResponse)
        async def index_html():
            return render_index()

        routers = settings["FASTAPI"]["routers"]
        for k, v in routers.items():
            if not v:
                continue
            v = property_from_module(v)
            self.fastapi_instance.include_router(v, prefix=f"/{k}", tags=[k])

    async def setup_lark(self):
        grammar = Path.cwd() / "grammar.lark"
        with open(grammar, "r") as f:
            data = f.read()
            parser = Lark(data)
            muforge.LOCKPARSER = parser

    async def setup_game_data(self):
        data_path = Path.cwd() / "data"
        schemas = muforge.SETTINGS["GAME"].get("data_schemas", dict())
        for dir_name, v in schemas.items():
            data_dir = data_path / dir_name
            # if it exists, grab all .toml files and load them.
            if not data_dir.exists():
                continue
            
            schema_classes = dict()
            def get_schema_classes(module_path: str):
                if (found := schema_classes.get(module_path, None)) is not None:
                    return found
                cls = property_from_module(module_path)
                schema_classes[module_path] = cls
                return cls

            # for each .toml file:
            for path in data_dir.glob("*.toml"):
                data = None
                with path.open("rb") as f:
                    data = tomllib.load(f)
                cls = get_schema_classes(v['class'])
                obj = cls(**data)
                if not isinstance(getattr(muforge, v['field'], None), dict):
                    setattr(muforge, v['field'], dict())
                store = getattr(muforge, v['field'])
                store[obj.id] = obj
            

    async def setup(self):
        await super().setup()
        muforge.EVENT_HUB = EventHub()
        await self.setup_game_data()
        await self.setup_lark()
        await self.setup_asyncpg()
        await self.setup_fastapi()

        for k, v in muforge.SETTINGS["GAME"].get("lockfuncs", dict()).items():
            lock_funcs = callables_from_module(v)
            for name, func in lock_funcs.items():
                muforge.LOCKFUNCS[name] = func

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
        async with muforge.PGPOOL.acquire() as conn:
            await conn.add_listener("table_changes", self.handle_postgre_notification)
            while True:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break

    async def system_pinger(self):
        from muforge.shared.events.system import SystemPing

        try:
            while True:
                await muforge.EVENT_HUB.broadcast(SystemPing())
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            return

    async def start(self):
        self.task_group.create_task(serve(self.fastapi_instance, self.fastapi_config))
        self.task_group.create_task(self.postgre_listener())
        self.task_group.create_task(self.system_pinger())
