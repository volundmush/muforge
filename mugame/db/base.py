import typing

import muforge  # assuming this is where PGPOOL is defined


def from_pool(func):
    """
    Wraps simple functions that just need a connection but not a transaction.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with muforge.PGPOOL.acquire() as conn:
            return await func(conn, *args, **kwargs)

    return wrapper
