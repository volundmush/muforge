from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import mudforge
import jwt
import typing
import uuid
import pydantic

from asyncpg.exceptions import UniqueViolationError

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from ..db.models import UserModel, CharacterModel
from ..db import auth as auth_db
from .utils import crypt_context, oauth2_scheme, get_real_ip, get_current_user, ActiveAs

router = APIRouter()


class UserLogin(BaseModel):
    email: pydantic.EmailStr
    password: str


def _create_token(sub: str, expires: datetime, refresh: bool = False):
    data = {
        "sub": sub,
        "exp": expires,
        "iat": datetime.now(tz=timezone.utc),
    }
    if refresh:
        data["refresh"] = True
    jwt_settings = mudforge.SETTINGS["JWT"]
    return jwt.encode(data, jwt_settings["secret"], algorithm=jwt_settings["algorithm"])


def create_token(sub: str):
    jwt_settings = mudforge.SETTINGS["JWT"]
    return _create_token(
        sub,
        datetime.now(tz=timezone.utc)
        + timedelta(minutes=jwt_settings["token_expire_minutes"]),
    )


def create_refresh(sub: str):
    jwt_settings = mudforge.SETTINGS["JWT"]
    return _create_token(
        sub,
        datetime.now(tz=timezone.utc)
        + timedelta(minutes=jwt_settings["refresh_expire_minutes"]),
        True,
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    @classmethod
    def from_uuid(cls, id: uuid.UUID) -> "TokenResponse":
        sub = str(id)
        token = create_token(sub)
        refresh = create_refresh(sub)
        return cls(access_token=token, refresh_token=refresh, token_type="bearer")


async def handle_login(request: Request, email: str, password: str) -> TokenResponse:
    ip = get_real_ip(request)
    user_agent = request.headers.get("User-Agent", None)

    result = await auth_db.authenticate_user(email, password, ip, user_agent)
    return TokenResponse.from_uuid(result.id)


@router.post("/register", response_model=TokenResponse)
async def register(request: Request, data: Annotated[UserLogin, Body()]):

    try:
        hashed = crypt_context.hash(data.password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error hashing password."
        )

    user = await auth_db.register_user(data.email, hashed)
    token = TokenResponse.from_uuid(user.id)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    return await handle_login(request, data.username, data.password)


class RefreshTokenModel(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(ref: Annotated[RefreshTokenModel, Body()]):
    jwt_settings = mudforge.SETTINGS["JWT"]
    try:
        payload = jwt.decode(
            ref.refresh_token,
            jwt_settings["secret"],
            algorithms=[jwt_settings["algorithm"]],
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )
        # Get user identifier from token. For example:
    if not payload.get("refresh", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )
    if (sub := payload.get("sub", None)) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload."
        )

    # Verify user exists. This will raise if not.
    user = await auth_db.get_user(sub)

    return TokenResponse.from_uuid(sub)
