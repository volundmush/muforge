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

from .utils import (
    crypt_context,
    oauth2_scheme,
    get_real_ip,
    get_current_user,
    get_acting_character,
    streaming_list
)
from ..db.models import UserModel, CharacterModel, ActiveAs
from ..db import characters as characters_db

router = APIRouter()


@router.get("/", response_model=typing.List[CharacterModel])
async def get_characters(user: Annotated[UserModel, Depends(get_current_user)]):
    if not user.admin_level > 0:
        raise HTTPException(
            status_code=403, detail="You do not have permission to view all characters."
        )
    
    stream = await characters_db.list_characters()

    return streaming_list(stream)


@router.get("/{character_id}", response_model=CharacterModel)
async def get_character(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    character = await characters_db.find_character_id(character_id)
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
    result = await characters_db.create_character(user, char_data.name)
    return result