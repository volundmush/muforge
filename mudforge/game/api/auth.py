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

from .models import UserModel, CharacterModel
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


async def handle_login(
    request: Request, password: str, user: uuid.UUID
) -> TokenResponse:
    ip = get_real_ip(request)
    user_agent = request.headers.get("User-Agent", None)

    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            # Retrieve the latest password row for this user.
            password_row = await conn.fetchrow(
                """
                SELECT password
                FROM user_passwords
                WHERE user_id = $1
                """,
                user,
            )
            if not (
                password_row
                and password_row["password"]
                and crypt_context.verify(password, password_row["password"])
            ):
                await conn.execute(
                    """
                    INSERT INTO loginrecords (user_id, ip_address, success, user_agent)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user,
                    ip,
                    False,
                    user_agent,
                )
                raise HTTPException(status_code=400, detail="Invalid credentials.")

            # Record successful login.
            await conn.execute(
                """
                INSERT INTO loginrecords (user_id, ip_address, success, user_agent)
                VALUES ($1, $2, $3, $4)
                """,
                user,
                ip,
                True,
                user_agent,
            )

    # Create tokens based on the user's email.
    return TokenResponse.from_uuid(user)


async def register_user(email: str, hashed_password: str) -> uuid.UUID:
    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            try:
                # Insert the new user.
                user_row = await conn.fetchrow(
                    """
                    INSERT INTO users (email)
                    VALUES ($1)
                    RETURNING id
                    """,
                    email,
                )
            except UniqueViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists.",
                )
            user_id = user_row["id"]

            # Insert the password record.
            password_row = await conn.fetchrow(
                """
                INSERT INTO passwords (user_id, password)
                VALUES ($1, $2)
                RETURNING id
                """,
                user_id,
                hashed_password,
            )
            password_id = password_row["id"]

            # Update the user to set the current password.
            await conn.execute(
                "UPDATE users SET current_password_id=$1 WHERE id=$2",
                password_id,
                user_id,
            )
            return user_id


@router.post("/register", response_model=TokenResponse)
async def register(request: Request, data: Annotated[UserLogin, Body()]):
    data.password = data.password.strip()
    ip = get_real_ip(request)
    user_agent = request.headers.get("User-Agent", None)

    try:
        hashed = crypt_context.hash(data.password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error hashing password."
        )

    user = await register_user(str(data.email).lower().strip(), hashed)
    token = TokenResponse.from_uuid(user)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    data.password = data.password.strip()

    async with mudforge.PGPOOL.acquire() as conn:
        if not (
            user := await conn.fetchrow(
                "SELECT id FROM users WHERE email = $1", data.username
            )
        ):
            raise HTTPException(status_code=400, detail="Invalid credentials.")

    return await handle_login(request, data.password, user["id"])


class CharacterLogin(BaseModel):
    name: str
    password: str


class CharacterTokenResponse(TokenResponse):
    character: int


@router.post("/play", response_model=CharacterTokenResponse)
async def play(request: Request, data: Annotated[CharacterLogin, Body()]):
    data.name = data.name.lower().strip()
    data.password = data.password.strip()

    async with mudforge.PGPOOL.acquire() as conn:
        character_row = await conn.fetchrow(
            """
            SELECT c.id,c.user_id
            FROM characters c
            WHERE c.name = $1
            """,
            data.name,
        )
    if not character_row:
        raise HTTPException(status_code=400, detail="Invalid credentials.")

    result = await handle_login(request, data.password, character_row["user_id"])
    return CharacterTokenResponse(character=character_row["id"], **result.dict())


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(ref: str):
    jwt_settings = mudforge.SETTINGS["JWT"]
    try:
        payload = jwt.decode(
            ref, jwt_settings["secret"], algorithms=[jwt_settings["algorithm"]]
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
    async with mudforge.PGPOOL.acquire() as conn:
        if not (
            user_row := await conn.fetchrow("SELECT id FROM users WHERE id = $1", sub)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

    return TokenResponse.from_uuid(sub)
