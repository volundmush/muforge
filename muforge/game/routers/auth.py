from typing import Annotated

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

import muforge
from muforge.shared.models.auth import RefreshTokenModel, TokenResponse, UserLogin
from muforge.shared.utils import crypt_context

from ..db import auth as auth_db
from ..db import users as users_db

router = APIRouter()


async def handle_login(request: Request, username: str, password: str) -> TokenResponse:
    ip = request.client.host
    user_agent = request.headers.get("User-Agent", None)

    result = await auth_db.authenticate_user(username, password, ip, user_agent)
    return TokenResponse.from_uuid(result.id)


@router.post("/register", response_model=TokenResponse)
async def register(request: Request, data: Annotated[UserLogin, Body()]):

    user = await auth_db.register_user(data.username, data.password.get_secret_value())
    token = TokenResponse.from_uuid(user.id)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    return await handle_login(request, data.username, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(ref: Annotated[RefreshTokenModel, Body()]):
    jwt_settings = muforge.SETTINGS["JWT"]
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
    user = await users_db.get_user(sub)

    return TokenResponse.from_uuid(sub)
