import muforge
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
        #self.task_group.create_task(self.postgre_listener())
        self.task_group.create_task(self.system_pinger())
