import typing
import uuid

from asyncpg import Connection
from fastapi import HTTPException, status

from muforge.shared.models import UserModel

from .base import from_pool, stream


@from_pool
async def get_user(conn: Connection, user_id: uuid.UUID) -> UserModel:
    user_data = await conn.fetchrow(
        """
        SELECT *
        FROM users
        WHERE id = $1 LIMIT 1
        """,
        user_id,
    )
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserModel(**user_data)


@from_pool
async def find_user(conn: Connection, username: str) -> UserModel:
    user_data = await conn.fetchrow(
        """
        SELECT *
        FROM users
        WHERE username = $1 LIMIT 1
        """,
        username,
    )
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserModel(**user_data)


@stream
async def list_users(conn: Connection) -> typing.AsyncGenerator[UserModel, None]:
    query = "SELECT * FROM users"
    async for row in conn.cursor(query):
        yield UserModel(**row)
