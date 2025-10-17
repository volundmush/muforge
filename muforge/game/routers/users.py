from typing import Annotated

import typing
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from .utils import (
    get_current_user,
    streaming_list,
)

from muforge.shared.models.users import UserModel
from muforge.shared.models.characters import CharacterModel
from muforge.game.db import characters as characters_db
from ..db import users as users_db

router = APIRouter()


@router.get("/", response_model=typing.List[UserModel])
async def get_users(user: Annotated[UserModel, Depends(get_current_user)]):
    if user.admin_level < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions."
        )

    users = users_db.list_users()
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


@router.get("/{user_id}/characters", response_model=typing.List[CharacterModel])
async def get_user_characters(
    user_id: uuid.UUID, user: Annotated[UserModel, Depends(get_current_user)]
):
    if user.id != user_id and user.admin_level < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions."
        )

    target_user = await users_db.get_user(user_id)

    characters = characters_db.list_characters_user(target_user)
    return streaming_list(characters)
