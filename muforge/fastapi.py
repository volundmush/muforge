import logging
import sys
import typing
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable
from uuid import uuid4

import asyncpg
import orjson
import pydantic
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from loguru import logger
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


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


async def create_pool(settings: dict):
    pool = await asyncpg.create_pool(init=init_connection, **settings)
    return pool


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        # Map stdlib level to loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(logger=record.name).opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    mode: str,
    level: str = "INFO",
    rotation: str = "20 MB",
    retention: str = "14 days",
    compression: str | None = None,
):
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{mode}.log"

    # Intercept stdlib logging (including hypercorn/uvicorn)
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=logging.getLevelName(level.upper()),
        force=True,
    )

    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )
    logger.add(
        log_path,
        level=level.upper(),
        rotation=rotation,
        retention=retention,
        compression=compression,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )


def create_app(
    mode: str, fastapi_settings: dict, game_settings: dict, postgre: bool = True
):
    setup_logging(
        mode=mode,
        level=game_settings.get("LOG_LEVEL", "INFO"),
        rotation=game_settings.get("LOG_ROTATION", "20 MB"),
        retention=game_settings.get("LOG_RETENTION", "14 days"),
        compression=game_settings.get("LOG_COMPRESSION"),  # e.g., "zip"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[dict]:
        app.state.settings = game_settings
        pool = None
        if postgre:
            pool = await create_pool(game_settings["POSTGRES"])
        app.state.pg_pool = pool
        logger.bind(component=mode).info("Application startup complete")
        try:
            yield {"pg_pool": pool}
        finally:
            if postgre and pool is not None:
                await pool.close()
            logger.bind(component=mode).info("Application shutdown complete")

    app = FastAPI(lifespan=lifespan, **fastapi_settings)

    # Proxy headers first so downstream sees real client info.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="127.0.0.1,10.0.0.0/8")

    # Host validation.
    allowed_hosts = game_settings.get("ALLOWED_HOSTS", ["*"])
    if allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Compression (not enabled by default in FastAPI).
    app.add_middleware(GZipMiddleware, minimum_size=1024)

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

    return app


async def get_pg_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pg_pool


async def get_pg_conn(
    pool: asyncpg.Pool = Depends(get_pg_pool),
) -> typing.AsyncGenerator[asyncpg.Connection, None]:
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


async def json_array_generator(
    data: typing.AsyncGenerator[pydantic.BaseModel, None],
) -> typing.AsyncGenerator[str, None]:
    # Start the JSON array
    yield "["
    first = True
    # Stream the rows from the DB
    async for element in data:
        # Insert commas between elements
        if not first:
            yield ","
        else:
            first = False
        # Convert your Pydantic model to JSON. (Assumes CharacterModel has .json())
        yield element.model_dump_json()
    # End the JSON array
    yield "]"


def streaming_list(
    data: typing.AsyncGenerator[pydantic.BaseModel, None],
) -> StreamingResponse:
    return StreamingResponse(
        json_array_generator(data),
        media_type="application/json",
    )


def transaction(func):
    """
    Executes the function within a transaction.

    For streaming a select, use @stream not @transaction.
    """

    @wraps(func)
    async def wrapper(conn, *args, **kwargs):
        async with conn.transaction():
            # Pass the connection as the first parameter to the function.
            return await func(conn, *args, **kwargs)

    return wrapper


def stream(func):
    """
    Streams results asynchronously from a query. Don't use @transaction for that, use this.
    """

    @wraps(func)
    def wrapper(conn, *args, **kwargs) -> typing.AsyncIterator[typing.Any]:
        async def generator():
            async with conn.transaction():
                # If `func` is an async generator, we must iterate over it:
                async for item in func(conn, *args, **kwargs):
                    yield item

        # Return the async generator object
        return generator()

    return wrapper
