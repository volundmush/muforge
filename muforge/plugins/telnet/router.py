import typing
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


class MSSPResponse(BaseModel):
    data: tuple[tuple[str, str], ...] = Field(default_factory=lambda: ())


router = APIRouter()


@router.get("/", response_model=MSSPResponse)
async def get_mssp(request: Request):
    app = request.app.state.application
    return MSSPResponse()
