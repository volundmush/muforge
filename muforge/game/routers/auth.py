from typing import Annotated

import mudforge
import jwt

from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from muforge.shared.models.auth import TokenResponse, UserLogin, RefreshTokenModel

from ..db import users as users_db, auth as auth_db
from muforge.shared.utils import crypt_context
from .utils import get_real_ip

router = APIRouter()


async def handle_login(request: Request, email: str, password: str) -> TokenResponse:
    ip = get_real_ip(request)
    user_agent = request.headers.get("User-Agent", None)

    result = await auth_db.authenticate_user(email, password, ip, user_agent)
    return TokenResponse.from_uuid(result.id)


@router.post("/register", response_model=TokenResponse)
async def register(request: Request, data: Annotated[UserLogin, Body()]):

    try:
        hashed = crypt_context.hash(data.password.get_secret_value())
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
    user = await users_db.get_user(sub)

    return TokenResponse.from_uuid(sub)
