from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import orjson
import typing
import mudforge
import jwt
import uuid
import pydantic

from rich.text import Text
from rich.markup import MarkupError
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

class RichTextModel(pydantic.BaseModel):
    text: str


@router.get("/verify_rich_text")
async def verify_rich_text(
    request: Request,
    user: Annotated[UserModel, Depends(get_current_user)],
    test_text: Annotated[RichTextModel, Body()],
):
    """
    Verify that the rich text is valid.
    """
    try:
        text = Text.from_markup(test_text.text)
    except MarkupError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}