import asyncio
import tomllib
from pathlib import Path

import asyncpg
import orjson
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from hypercorn import Config
from hypercorn.asyncio import serve
from lark import Lark
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from fastapi import Depends, FastAPI, Request, Response

import muforge
from muforge.application import Application as OldApplication
from muforge.utils.misc import callables_from_module, property_from_module


def decode_json(data: bytes):
    decoded = orjson.loads(data)
    return decoded


async def init_connection(conn: asyncpg.Connection):
    for scheme in ("json", "jsonb"):
        await conn.set_type_codec(
            scheme,  # The PostgreSQL type to target.
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
        settings = muforge.SETTINGS["POSTGRESQL"]
        pool = await asyncpg.create_pool(init=init_connection, **settings)
        muforge.PGPOOL = pool

    async def setup_commands(self):
        for k, v in muforge.SETTINGS["GAME"]["commands"].items():
            for name, command in callables_from_module(v).items():
                muforge.GAME_COMMANDS[command.name] = command
                muforge.GAME_COMMANDS_PRIORITY[command.priority].append(command)

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

        # Compression (not enabled by default in FastAPI).
        app.add_middleware(GZipMiddleware, minimum_size=1024)

        # Proxy headers first so downstream sees real client info.
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="127.0.0.1,10.0.0.0/8")

        @app.middleware("http")
        async def request_id_middleware(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            incoming = request.headers.get("X-Request-ID")
            request_id = incoming or uuid4().hex
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers.setdefault("X-Request-ID", request_id)
            return response

        @app.middleware("http")
        async def security_headers_middleware(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            response = await call_next(request)
            # Add conservative defaults if not already set.
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault(
                "Referrer-Policy", "strict-origin-when-cross-origin"
            )
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault(
                "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
            )
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
            return response

        cwd = Path.cwd()
        static_dir = cwd / "static"
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        def render_index() -> HTMLResponse:
            index_path = cwd / "index.html"
            if not index_path.exists():
                return HTMLResponse(
                    "<h1>Muforge Web UI</h1><p>Put index.html in muforge/</p>",
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
        path = Path.cwd() / "data"

        locations_path = path / "locations.toml"
        if locations_path.exists():
            with open(locations_path, "rb") as f:
                data = tomllib.load(f)
                loc_class = muforge.CLASSES["location"]
                for k, v in data.items():
                    muforge.LOCATIONS[k] = loc_class(id=k, **v)

        objects_path = path / "objects.toml"
        if objects_path.exists():
            with open(objects_path, "rb") as f:
                data = tomllib.load(f)

    async def setup_typeclasses(self):
        typeclasses = muforge.SETTINGS["GAME"].get("typeclasses", dict())
        for k, v in typeclasses.items():
            cls = property_from_module(v)
            muforge.ENTITY_CLASSES[k] = cls

    async def setup_load_database(self):
        pass

    async def setup(self):
        await super().setup()
        await self.setup_game_data()
        await self.setup_lark()
        await self.setup_asyncpg()
        await self.setup_fastapi()
        await self.setup_commands()
        await self.setup_typeclasses()

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

        await self.setup_load_database()

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
                for k, v in muforge.SESSIONS.items():
                    await v.send_event(SystemPing())
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            return

    async def start(self):
        self.task_group.create_task(serve(self.fastapi_instance, self.fastapi_config))
        self.task_group.create_task(self.postgre_listener())
        self.task_group.create_task(self.system_pinger())
