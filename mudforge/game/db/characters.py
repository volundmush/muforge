import mudforge
import jwt
import typing
import uuid

from datetime import datetime, timedelta, timezone
from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status
from .base import transaction, from_pool, stream
from .models import UserModel, CharacterModel


@from_pool
async def find_character_name(conn: Connection, name: str) -> CharacterModel:
    query = "SELECT * FROM characters WHERE name = $1 AND deleted_at IS NULL"
    row = await conn.fetchrow(query, name)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Character not found"
        )
    return CharacterModel(**row)


@from_pool
async def find_character_id(
    conn: Connection, character_id: uuid.UUID
) -> CharacterModel:
    query = "SELECT * FROM characters WHERE id = $1"
    row = await conn.fetchrow(query, character_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Character not found"
        )
    return CharacterModel(**row)


@stream
async def list_characters(
    conn: Connection,
) -> typing.AsyncGenerator[CharacterModel, None]:
    query = "SELECT * FROM characters"
    # Use a cursor to stream results rather than loading everything into memory at once.
    async for row in conn.cursor(query):
        yield CharacterModel(**row)


@stream
async def list_characters_user(
    conn: Connection, user: UserModel
) -> typing.AsyncGenerator[CharacterModel, None]:
    query = "SELECT * FROM characters WHERE user_id = $1 AND deleted_at IS NULL"
    async for row in conn.cursor(query, user.id):
        yield CharacterModel(**row)


@from_pool
async def create_character(
    conn: Connection, user: UserModel, name: str
) -> CharacterModel:
    query = "INSERT INTO characters (name, user_id) VALUES ($1, $2) RETURNING *"
    try:
        row = await conn.fetchrow(query, name, user.id)
    except UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Character name already in use"
        )
    return CharacterModel(**row)
