import typing
import uuid
from typing import Annotated

import jwt
import pydantic
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer

import muforge

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

from muforge.mugame.db import pcs as pcs_db
from muforge.shared.models.pcs import ActiveAs
from muforge.shared.models.users import UserModel





async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    jwt_settings = muforge.SETTINGS["JWT"]
    try:
        payload = jwt.decode(
            token, jwt_settings["secret"], algorithms=[jwt_settings["algorithm"]]
        )
        if (user_id := payload.get("sub", None)) is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        raise credentials_exception

    user = muforge.USERS.get(uuid.UUID(user_id), None)

    if user is None:
        raise credentials_exception

    return user


async def get_acting_character(user: UserModel, character_id: uuid.UUID) -> ActiveAs:
    character = await characters_db.find_character_id(character_id)
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Character does not belong to you.")

    act = ActiveAs(user=user, character=character)
    return act
