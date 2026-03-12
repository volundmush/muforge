import typing
import uuid

import pydantic
from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status

import muforge

from .fields import pc_name
from .mixins import SoftDeleteMixin
from .users import UserModel


class PCModel(SoftDeleteMixin):
    id: uuid.UUID
    user_id: uuid.UUID
    name: pc_name


class CharacterCreate(pydantic.BaseModel):
    name: pc_name


class ActiveAs(pydantic.BaseModel):
    user: UserModel
    pc: PCModel


async def find_pc_name(conn: Connection, name: str) -> PCModel:
    query = "SELECT * FROM pcs WHERE name = $1 AND deleted_at IS NULL"
    row = await conn.fetchrow(query, name)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player Character not found"
        )
    return PCModel(**row)


async def find_pc_id(conn: Connection, character_id: uuid.UUID) -> PCModel:
    query = "SELECT * FROM pcs WHERE id = $1"
    row = await conn.fetchrow(query, character_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player Character not found"
        )
    return PCModel(**row)


# Meant to be used as a Stream
async def list_pcs(
    conn: Connection,
) -> typing.AsyncGenerator[PCModel, None]:
    query = "SELECT * FROM pcs"
    # Use a cursor to stream results rather than loading everything into memory at once.
    async for row in conn.cursor(query):
        yield PCModel(**row)


# Meant to be used as a Stream
async def list_pcs_user(
    conn: Connection, user: UserModel
) -> typing.AsyncGenerator[PCModel, None]:
    query = "SELECT * FROM pcs WHERE user_id = $1 AND deleted_at IS NULL"
    async for row in conn.cursor(query, user.id):
        yield PCModel(**row)


async def create_pc(conn: Connection, user: UserModel, name: str) -> PCModel:
    query = "INSERT INTO pcs (name, user_id) VALUES ($1, $2) RETURNING *"
    try:
        row = await conn.fetchrow(query, name, user.id)
    except UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Player Character name already in use",
        )
    return PCModel(**row)


# meant to be used as a transaction
async def list_online(conn: Connection) -> list[ActiveAs]:
    active_ids = muforge.EVENT_HUB.online()
    query = "SELECT * FROM pcs_active WHERE id = ANY($1)"
    character_rows = await conn.fetch(query, active_ids)
    characters = [PCModel(**row) for row in character_rows]
    user_ids = {c.user_id for c in characters}
    query = "SELECT * FROM users WHERE id = ANY($1)"
    user_rows = await conn.fetch(query, user_ids)

    user_dict = {u["id"]: UserModel(**u) for u in user_rows}

    return [
        ActiveAs(pc=character, user=user_dict[character.user_id])
        for character in characters
    ]
