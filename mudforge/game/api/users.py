from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import typing
import mudforge
import jwt
import uuid
import pydantic

from asyncpg import exceptions
from pydantic import BaseModel


from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from .utils import crypt_context, oauth2_scheme, get_real_ip, get_current_user, streaming_list
from ..db.models import UserModel, CharacterModel, ActiveAs
from ..db import characters as characters_db, users as users_db

router = APIRouter()


@router.get("/", response_model=typing.List[UserModel])
async def get_users(user: Annotated[UserModel, Depends(get_current_user)]):
    if user.admin_level < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions."
        )
    
    users = await users_db.list_users()
    return streaming_list(users)


@router.get("/{user_id}", response_model=UserModel)
async def get_user(
    user_id: uuid.UUID, user: Annotated[UserModel, Depends(get_current_user)]
):
    if user.admin_level < 1 and user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions."
        )
    
    found = await users_db.get_user(user_id)
    return found


@router.get("/{user_id}/characters")
async def get_user_characters(
    user_id: uuid.UUID, user: Annotated[UserModel, Depends(get_current_user)]
):
    if user.id != user_id and user.admin_level < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions."
        )

    characters = await characters_db.list_characters_user(user_id)
    return streaming_list(characters)
