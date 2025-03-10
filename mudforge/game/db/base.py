from functools import wraps
import mudforge  # assuming this is where PGPOOL is defined

def transaction(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with mudforge.PGPOOL.acquire() as conn:
            async with conn.transaction():
                # Pass the connection as the first parameter to the function.
                return await func(conn, *args, **kwargs)
    return wrapper

def from_pool(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with mudforge.PGPOOL.acquire() as conn:
            return await func(conn, *args, **kwargs)
    return wrapper