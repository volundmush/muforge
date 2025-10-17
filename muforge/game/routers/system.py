from typing import Annotated

import pydantic

from rich.text import Text
from rich.markup import MarkupError
from fastapi import APIRouter, Depends, Body, HTTPException, Request

from .utils import (
    get_current_user,
)

from muforge.shared.models.users import UserModel

router = APIRouter()


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
