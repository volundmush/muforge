import asyncio
import tomllib
import typing
from collections import defaultdict
from pathlib import Path

import asyncpg
import orjson
from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from hypercorn import Config
from hypercorn.asyncio import serve
from lark import Lark
from loguru import logger
from mufroge.utils.database import INIT_SQL, transaction
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import muforge
from muforge.application import BaseApplication
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


@transaction
async def perform_migrations(conn: asyncpg.Connection, app):
    # INIT_SQL creates the plugin_migrations table.
    await conn.execute(INIT_SQL)

    all_migrations = list()
    migrations = dict()

    for p in app.plugin_load_order:
        mi = p.game_migrations()
        migrations[p.slug()] = mi
        for k, v in mi.items():
            all_migrations.append((p.slug(), k, v))

    migration_order: list[tuple[str, str, typing.Any]] = list()

    remaining_migrations = all_migrations.copy()

    resolved: set[tuple[str, str]] = set()

    while remaining_migrations:
        idx_remove = list()
        for i, m in enumerate(remaining_migrations):
            # each element in dep is a pair of (plugin_slug, migration_name)
            dep = getattr(m[2], "depends", list())
            has_deps = True
            for p_slug, m_name in dep:
                if (p_slug, m_name) not in resolved:
                    has_deps = False
                    break
            if has_deps:
                # We passed all checks.
                migration_order.append(m)
                resolved.add((m[0], m[1]))
                idx_remove.append(i)
        for i in reversed(idx_remove):
            remaining_migrations.pop(i)

    # We now have the list of sorted migrations to perform in order.
    # Some of them may have already been performed.

    performed = 0
    for plugin_slug, migration_name, migration in migration_order:
        exists = await conn.fetchrow(
            """
            SELECT applied_at FROM plugin_migrations
            WHERE plugin_slug = $1 AND migration_name = $2
        """,
            plugin_slug,
            migration_name,
        )
        if exists:
            continue
        up = getattr(migration, "upgrade", None)

        # up can either be a string, none, or an async callable that should take the connection object.
        if isinstance(up, str):
            await conn.execute(up)
            performed += 1
        elif callable(up):
            await up(conn)
            performed += 1
        else:
            logger.warning(
                f"Migration {migration_name} of plugin {plugin_slug} has no upgrade path. Skipping."
            )
            continue

    logger.info(f"Performed {performed} migrations.")


class Application(BaseApplication):
    name = "game"

    def __init__(self, settings):
        super().__init__(settings)
        self.fastapi_config = None
        self.fastapi_instance = None

    async def setup_asyncpg(self):
        postgre_settings = self.settings["postgresql"]
        pool = await asyncpg.create_pool(init=init_connection, **postgre_settings)
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
        app.state.application = self

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

        v1 = APIRouter()
        routers = dict()
        for p in self.plugin_load_order:
            if p_routers := p.game_routers():
                for k, v in p_routers.items():
                    if k in routers:
                        logger.error(
                            f"Plugin {p.slug()} defines router for prefix /{k}, but it is already defined by another plugin."
                        )
                        raise Exception(
                            f"Plugin {p.slug()} defines router for prefix /{k}, but it is already defined by another plugin."
                        )
                    routers[k] = v

        for k, v in routers.items():
            if not v:
                continue
            v = property_from_module(v)
            v1.include_router(v, prefix=f"/{k}", tags=[k])
        app.include_router(v1, prefix="/v1")

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
        await perform_migrations(self)
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
