import mudforge
import jwt
import uuid
import pydantic
import orjson
from datetime import datetime
from dataclasses import dataclass
from typing import Annotated, Optional
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Request, Depends, HTTPException, status

crypt_context = CryptContext(schemes=["argon2"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

from .models import UserModel, CharacterModel, ActiveAs


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


async def get_acting_character(user: UserModel, character_id: int) -> ActiveAs:
    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            character_data = await conn.fetchrow(
                "SELECT * FROM characters WHERE id = $1", character_id
            )
            if character_data is None:
                raise HTTPException(status_code=404, detail="Character not found")
            character = CharacterModel(**character_data)
            if character.user_id != user.id:
                raise HTTPException(
                    status_code=403, detail="Character does not belong to you."
                )
            active = await conn.fetchrow(
                "SELECT * FROM characters_active_view WHERE id = $1", character.id
            )
            if not active:
                spoof = await conn.fetchrow(
                    "SELECT * from character_spoofs WHERE character_id = $1 AND spoofed_name = $2",
                    character.id,
                    character.name,
                )
                if not spoof:
                    spoof = await conn.fetchrow(
                        "INSERT INTO character_spoofs (character_id, spoofed_name) VALUES ($1, $2) RETURNING *",
                        character.id,
                        character.name,
                    )
                new_active = await conn.fetchrow(
                    "INSERT INTO characters_active (id, spoofing_id) VALUES ($1, $2) RETURNING *",
                    character.id,
                    spoof["id"],
                )
                active = await conn.fetchrow(
                    "SELECT * FROM characters_active_view WHERE id = $1", character.id
                )
            await conn.execute(
                "UPDATE characters SET last_active_at=now() WHERE id=$1",
                character_id,
            )
            act = ActiveAs(
                user=user,
                character=character,
                admin_level=active["admin_level"],
                spoofed_name=active["spoofed_name"],
                spoofing_id=active["spoofing_id"],
                metadata=active["metadata"],
                active_created_at=active["active_created_at"],
            )
            return act
