import mudforge
import jwt
import uuid
import pydantic
import orjson
import typing
from datetime import datetime
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from mudforge.utils import crypt_context

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

from mudforge.models.users import UserModel
from mudforge.models.characters import CharacterModel, ActiveAs

from ..db import characters as characters_db

async def json_array_generator(data: typing.AsyncGenerator[pydantic.BaseModel, None]) -> typing.AsyncGenerator[str, None]:
        # Start the JSON array
        yield "["
        first = True
        # Stream the rows from the DB
        async for element in data:
            # Insert commas between elements
            if not first:
                yield ","
            else:
                first = False
            # Convert your Pydantic model to JSON. (Assumes CharacterModel has .json())
            yield element.model_dump_json()
        # End the JSON array
        yield "]"

def streaming_list(data: typing.AsyncGenerator[pydantic.BaseModel, None]) -> StreamingResponse:
    return StreamingResponse(
        json_array_generator(data),
        media_type="application/json",
    )

def get_real_ip(request: Request):
    """
    If the request is behind a trusted proxy, then we'll trust X-Forwarded-For and use the first IP in the list.
    trusted proxies are in mudforge.SETTINGS["GAME"]["networking"]["trusted_proxy_ips"]
    """
    ip = request.client.host
    if ip in mudforge.SETTINGS["GAME"]["networking"]["trusted_proxy_ips"]:
        ip = request.headers.get("X-Forwarded-For", ip).split(",")[0].strip()
    return ip


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    jwt_settings = mudforge.SETTINGS["JWT"]
    try:
        payload = jwt.decode(
            token, jwt_settings["secret"], algorithms=[jwt_settings["algorithm"]]
        )
        if (user_id := payload.get("sub", None)) is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        raise credentials_exception

    async with mudforge.PGPOOL.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if user is None:
        raise credentials_exception

    return UserModel(**user)


async def get_acting_character(user: UserModel, character_id: uuid.UUID) -> ActiveAs:
    character = await characters_db.find_character_id(character_id)
    if character.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Character does not belong to you."
        )
    
    act = ActiveAs(
        user=user,
        character=character
    )
    return act
