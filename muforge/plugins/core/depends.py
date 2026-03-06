import typing
import uuid
from typing import Annotated

import jwt
import pydantic
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


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

    async with muforge.PGPOOL.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if user is None:
        raise credentials_exception

    return UserModel(**user)


async def get_acting_character(user: UserModel, character_id: uuid.UUID) -> ActiveAs:
    character = await pcs_db.find_pc_id(character_id)
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Character does not belong to you.")

    act = ActiveAs(user=user, character=character)
    return act
