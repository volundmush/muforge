from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import orjson
import typing
import mudforge
import jwt
import uuid
import pydantic

from asyncpg import exceptions
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from .utils import (
    crypt_context,
    oauth2_scheme,
    get_real_ip,
    get_current_user,
    get_acting_character,
)
from .models import UserModel, CharacterModel, ActiveAs

router = APIRouter()


@router.get("/", response_model=typing.List[CharacterModel])
async def get_characters(user: Annotated[UserModel, Depends(get_current_user)]):
    if not user.admin_level > 0:
        raise HTTPException(
            status_code=403, detail="You do not have permission to view all characters."
        )

    async with mudforge.PGPOOL.acquire() as conn:
        characters = await conn.fetch(
            "SELECT * FROM characters WHERE user_id = $1", user.id
        )

    return [CharacterModel(**c) for c in characters]


@router.get("/active", response_model=typing.List[CharacterModel])
async def get_characters_active(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        characters = await conn.fetch(
            "SELECT * FROM characters_active_view WHERE user_id = $1", user.id
        )

    return [CharacterModel(**c) for c in characters]


@router.get("/active/me", response_model=ActiveAs)
async def get_active_character_me(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)
    return acting


class ActiveUpdate(pydantic.BaseModel):
    admin_level: Optional[int] = None
    spoofed_name: Optional[str] = None
    metadata: Optional[dict[typing.Any, typing.Any]] = None


@router.patch("/active/{character_id}", response_model=ActiveAs)
async def set_active_character(
    user: Annotated[UserModel, Depends(get_current_user)],
    update: Annotated[ActiveUpdate, Body()],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            if update.admin_level is not None:
                admin_level = min(user.admin_level, update.admin_level)
                if admin_level != acting.admin_level:
                    await conn.execute(
                        "UPDATE characters_active SET admin_level = $1 WHERE id = $2",
                        admin_level,
                        character_id,
                    )
                    acting.admin_level = admin_level
            if update.metadata is not None:
                await conn.execute(
                    "UPDATE characters_active SET metadata = $1 WHERE id = $2",
                    update.metadata,
                    character_id,
                )
                acting.metadata = update.metadata
            if (
                update.spoofed_name is not None
                and update.spoofed_name != acting.spoofed_name
            ):
                spoof_id = await conn.fetchrow(
                    "SELECT id FROM character_spoofs WHERE character_id=$1 AND spoofed_name=$2",
                    character_id,
                    update.spoofed_name,
                )
                if not spoof_id:
                    spoof_id = await conn.fetchrow(
                        "INSERT INTO character_spoofs (character_id, spoofed_name) VALUES ($1, $2) RETURNING id",
                        character_id,
                        update.spoofed_name,
                    )
                await conn.execute(
                    "UPDATE characters_active SET spoofing_id = $1 WHERE id=$2",
                    spoof_id,
                    character_id,
                )
                acting.spoofing_id = spoof_id
                acting.spoofed_name = update.spoofed_name
            await conn.execute(
                "UPDATE characters SET last_active_at=now() WHERE id=$1", character_id
            )
    return acting


@router.get("/{character_id}", response_model=CharacterModel)
async def get_character(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    async with mudforge.PGPOOL.acquire() as conn:
        character_data = await conn.fetchrow(
            "SELECT * FROM characters WHERE id = $1", character_id
        )
    if character_data is None:
        raise HTTPException(status_code=404, detail="Character not found")
    character = CharacterModel(**character_data)
    if character.user_id != user.id and user.admin_level == 0:
        raise HTTPException(status_code=403, detail="Character does not belong to you.")
    return character


class CharacterCreate(pydantic.BaseModel):
    name: str


@router.post("/", response_model=CharacterModel)
async def create_character(
    user: Annotated[UserModel, Depends(get_current_user)],
    char_data: Annotated[CharacterCreate, Body()],
):
    async with mudforge.PGPOOL.acquire() as conn:
        try:
            character_id = await conn.fetchval(
                "INSERT INTO characters (user_id, name) VALUES ($1, $2) RETURNING id",
                user.id,
                char_data.name,
            )
        except exceptions.UniqueViolationError:
            raise HTTPException(status_code=400, detail="Character name already taken.")

        character_data = await conn.fetchrow(
            "SELECT * FROM characters WHERE id = $1", character_id
        )
    return CharacterModel(**character_data)
