from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import orjson
import typing
import mudforge
import jwt
import uuid
import pydantic

from asyncpg import exceptions
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse

from .utils import (
    crypt_context,
    oauth2_scheme,
    get_real_ip,
    get_current_user,
    get_acting_character,
)
from mudforge.utils import subscription, queue_iterator

from ..db.models import UserModel, CharacterModel, ActiveAs

router = APIRouter()


@router.get("/updates")
async def stream_updates(
    user: Annotated[UserModel, Depends(get_current_user)],
    request: Request,
):
    """
    Streams updates to the client.
    """
