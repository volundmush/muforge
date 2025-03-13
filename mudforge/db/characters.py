import typing
import uuid

from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status
from .base import transaction, from_pool, stream

import mudforge
from mudforge.models.users import UserModel
from mudforge.models.characters import CharacterModel, ActiveAs


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


@transaction
async def list_online(conn: Connection) -> list[ActiveAs]:
    active_ids = mudforge.EVENT_HUB.online()
    query = "SELECT * FROM characters WHERE id = ANY($1)"
    character_rows = await conn.fetch(query, active_ids)
    characters = [CharacterModel(**row) for row in character_rows]
    user_ids = {c.user_id for c in characters}
    query = "SELECT * FROM users WHERE id = ANY($1)"
    user_rows = await conn.fetch(query, user_ids)

    user_dict = {u["id"]: UserModel(**u) for u in user_rows}

    return [
        ActiveAs(character=character, user=user_dict[character.user_id])
        for character in characters
    ]
