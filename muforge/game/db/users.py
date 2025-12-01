import typing
import uuid

from asyncpg import Connection
from fastapi import HTTPException, status

import muforge
from muforge.shared.models.users import UserModel
from .base import from_pool, stream



@from_pool
async def get_user(conn: Connection, user_id: uuid.UUID) -> UserModel:
    if not (user := muforge.USERS.get(user_id, None)):
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
        user = UserModel(**user_data)
        muforge.USERS[user_id] = user
    return user


@from_pool
async def find_user(conn: Connection, email: str) -> UserModel:
    user_data = await conn.fetchrow(
        """
        SELECT id
        FROM users
        WHERE email = $1 LIMIT 1
        """,            
        email,
    )
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return await get_user(conn, user_data["id"])



@stream
async def list_users(conn: Connection) -> typing.AsyncGenerator[UserModel, None]:
    query = "SELECT * FROM users"
    async for row in conn.cursor(query):
        yield UserModel(**row)
