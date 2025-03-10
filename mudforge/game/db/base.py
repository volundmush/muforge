from functools import wraps
import typing
import mudforge  # assuming this is where PGPOOL is defined


def transaction(func):
    """
    Executes the function within a transaction.

    For streaming a select, use @stream not @transaction.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with mudforge.PGPOOL.acquire() as conn:
            async with conn.transaction():
                # Pass the connection as the first parameter to the function.
                return await func(conn, *args, **kwargs)

    return wrapper


def stream(func):
    """
    Streams results asynchronously from a query. Don't use @transaction for that, use this.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> typing.AsyncIterator[typing.Any]:
        async def generator():
            async with mudforge.PGPOOL.acquire() as conn:
                async with conn.transaction():
                    # If `func` is an async generator, we must iterate over it:
                    async for item in func(conn, *args, **kwargs):
                        yield item

        # Return the async generator object
        return generator()

    return wrapper


def from_pool(func):
    """
    Wraps simple functions that just need a connection but not a transaction.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with mudforge.PGPOOL.acquire() as conn:
            return await func(conn, *args, **kwargs)

    return wrapper
