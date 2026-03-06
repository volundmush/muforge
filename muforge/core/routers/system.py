from typing import Annotated

import pydantic
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from rich.errors import MarkupError
from rich.text import Text

from muforge.shared.models.users import UserModel
from muforge.utils.depends import (
    get_current_user,
)

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
