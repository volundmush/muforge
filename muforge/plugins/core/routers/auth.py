from typing import Annotated

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from ..db import auth as auth_db
from ..db import users as users_db
from ..db.auth import RefreshTokenModel, TokenResponse, UserLogin

router = APIRouter()


async def handle_login(request: Request, username: str, password: str) -> TokenResponse:
    ip = request.client.host
    user_agent = request.headers.get("User-Agent", None)

    crypt_context = request.app.state.core.crypt_context
    db = request.app.state.core.db

    async with db.transaction() as conn:
        result = await auth_db.authenticate_user(
            conn, crypt_context, username, password, ip, user_agent
        )
    return TokenResponse.from_uuid(result.id)


@router.post("/register", response_model=TokenResponse)
async def register(request: Request, data: Annotated[UserLogin, Body()]):
    crypt_context = request.app.state.core.crypt_context
    db = request.app.state.core.db

    async with db.transaction() as conn:
        user = await auth_db.register_user(
            conn, crypt_context, data.username, data.password.get_secret_value()
        )
    token = TokenResponse.from_uuid(user.id)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    return await handle_login(request, data.username, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, ref: Annotated[RefreshTokenModel, Body()]):
    core = request.app.state.core
    jwt_settings = core.settings.get("jwt", dict())

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

    db = request.app.state.core.db
    # Verify user exists. This will raise if not.
    async with db.connection() as conn:
        user = await users_db.get_user(conn, sub)

    return TokenResponse.from_uuid(sub)
