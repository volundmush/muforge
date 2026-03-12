from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

T = TypeVar("T")


class Database:
    def __init__(self, pool):
        self.pool = pool

    @asynccontextmanager
    async def connection(self):
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    def stream(
        self,
        func: Callable[..., AsyncGenerator[T, None]],
        *args,
        **kwargs,
    ) -> AsyncIterator[T]:
        """
        Usage example:
            return blah.db.stream(func, *args, **kwargs)
            Where func takes a connection then *args, **kwargs
        """

        async def iterator():
            async with self.transaction() as conn:
                async for item in func(conn, *args, **kwargs):
                    yield item

        return iterator()


INIT_SQL = """
CREATE TABLE IF NOT EXISTS plugin_migrations (
    plugin_slug VARCHAR(100) NOT NULL,
    migration_name VARCHAR(100) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (plugin_slug, migration_name)
);
"""
