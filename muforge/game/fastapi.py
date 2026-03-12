import typing
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from hypercorn import Config
from loguru import logger
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from muforge.utils.misc import callables_from_module, property_from_module


async def assemble_fastapi(parent, config: Config):
    app = FastAPI()
    app.state.application = parent

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
        request: Request,
        call_next: typing.Callable[[Request], typing.Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Request-ID")
        request_id = incoming or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        return response

    @app.middleware("http")
    async def security_headers_middleware(
        request: Request,
        call_next: typing.Callable[[Request], typing.Awaitable[Response]],
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

    webdir = Path.cwd() / "webserver"
    static_dir = webdir / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def render_index() -> HTMLResponse:
        index_path = webdir / "root" / "index.html"
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
    for p in parent.plugin_load_order:
        if p_routers := p.game_routers_v1():
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
        logger.info(f"Adding router for prefix /{k}")
        v1.include_router(v, prefix=f"/{k}", tags=[k])
    app.include_router(v1, prefix="/v1")

    return app
