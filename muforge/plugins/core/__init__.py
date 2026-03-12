import typing
import uuid
from collections import defaultdict
from pathlib import Path

import asyncpg
import orjson
from lark import Lark
from loguru import logger

from muforge.plugin import BasePlugin

from .database import INIT_SQL, Database


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


async def perform_migrations(conn: asyncpg.Connection, app):
    # INIT_SQL creates the plugin_migrations table.
    await conn.execute(INIT_SQL)

    all_migrations = list()
    migrations = dict()

    for p in app.plugin_load_order:
        if not hasattr(p, "game_migrations"):
            continue
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


class Core(BasePlugin):
    def __init__(self, app, settings=None):
        super().__init__(app, settings)
        self.crypt_context = None
        self.db = None
        self.active_sessions: dict[uuid.UUID, typing.Any] = dict()
        self.commands: dict[str, type] = dict()
        self.commands_priority: dict[int, list[type]] = defaultdict(list)
        self.lockparser = None
        self.lockfuncs: dict[str, typing.Awaitable] = dict()

    def name(self) -> str:
        return "MuForge Core"

    def slug(self) -> str:
        return "core"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        """
        Returns a list of tuples of (migration_name, migration_module)
        A migration module contains the following properties:

        upgrade, downgrade: either strings (SQL statements) or callables (async functions) that perform the migration.

        depends: a list of tuples of (plugin_slug, migration_name) that this migration depends on.
        The migrations will be run in the order of the dependencies.
        """
        from .migrations import version001

        return [("version001", version001)]

    def game_routers_v1(self) -> dict[str, typing.Any]:
        from .routers.auth import router as auth_router
        from .routers.pcs import router as pcs_router
        from .routers.users import router as users_router

        return {
            "/auth": auth_router,
            "/users": users_router,
            "/pcs": pcs_router,
        }

    def game_static(self) -> str | None:
        return "static"

    def game_lockfuncs(self) -> dict[str, typing.Any]:
        return dict()

    def portal_parsers(self) -> dict[str, type]:
        from .portal_parsers.auth import LoginParser
        from .portal_parsers.pc import PCParser
        from .portal_parsers.user import UserParser

        return {"auth": LoginParser, "user": UserParser, "pc": PCParser}

    def portal_services(self) -> dict[str, type]:
        from .portal_services.connection import ConnectionService

        return {"connection": ConnectionService}

    async def setup_final(self):
        self.app.fastapi_instance.state.core = self
        await self.setup_crypt()
        await self.setup_database()
        await self.setup_lockfuncs()
        # await self.setup_commands()

    async def setup_crypt(self):
        from passlib.context import CryptContext

        self.crypt_context = CryptContext(**self.settings.get("crypt", {}))

    async def setup_lark(self):
        grammar = Path.cwd() / "grammar.lark"
        with open(grammar, "r") as f:
            data = f.read()
            self.lockparser = Lark(data)

    async def setup_database(self):
        postgre_settings = self.settings["postgresql"]
        pool = await asyncpg.create_pool(init=init_connection, **postgre_settings)
        self.db = Database(pool)

        async with self.db.transaction() as conn:
            await perform_migrations(conn, self.app)

    async def setup_lockfuncs(self):
        for p in self.app.plugin_load_order:
            self.lockfuncs.update(p.game_lockfuncs())

    async def setup_commands(self):
        for p in self.plugin_load_order:
            for k, v in p.game_commands().items():
                for key, command in callables_from_module(v).items():
                    self.commands[command.key] = command
                    self.commands_priority[command.priority].append(command)


__all__ = ["Core"]
