from typing import Annotated

import muforge
import typing
import uuid

from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from .utils import get_current_user, get_acting_character, streaming_list

from muforge.shared.models.users import UserModel
from muforge.shared.models.characters import CharacterModel, ActiveAs, CharacterCreate
from muforge.game.db import characters as characters_db

router = APIRouter()


@router.get("/", response_model=typing.List[CharacterModel])
async def get_characters(user: Annotated[UserModel, Depends(get_current_user)]):
    if not user.admin_level > 0:
        raise HTTPException(
            status_code=403, detail="You do not have permission to view all characters."
        )

    stream = characters_db.list_characters()

    return streaming_list(stream)


@router.get("/{character_id}", response_model=CharacterModel)
async def get_character(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    character = await characters_db.find_character_id(character_id)
    if character.user_id != user.id and user.admin_level == 0:
        raise HTTPException(status_code=403, detail="Character does not belong to you.")
    return character


@router.get("/{character_id}/active", response_model=ActiveAs)
async def get_character_active_as(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)
    return acting


@router.get("/{character_id}/events")
async def stream_character_events(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    # We don't use it; but this verifies that user can control character.
    acting = await get_acting_character(user, character_id)

    async def event_generator():
        queue = muforge.EVENT_HUB.subscribe(character_id)
        graceful = False
        try:
            # blocks until a new event
            while item := await queue.get():
                yield f"event: {item.__class__.__name__}\ndata: {item.model_dump_json()}\n\n"
            graceful = True
        finally:
            muforge.EVENT_HUB.unsubscribe(character_id, queue)
            if not graceful:
                pass  # this can do something later.

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class CommandSubmission(BaseModel):
    command: str


@router.post("/{character_id}/command")
async def submit_command(
        user: Annotated[UserModel, Depends(get_current_user)],
        character_id: uuid.UUID,
        command: Annotated[CommandSubmission, Body()],
):
    if character_id not in user.characters:
        raise HTTPException(
            status_code=403, detail="You do not have permission to use this character."
        )

    if not (session := muforge.SESSIONS.get(character_id, None)):
        raise HTTPException(
            status_code=404, detail="Character entity not found."
        )

    await session.execute_command(command.command)

    return {"status": "ok"}

@router.post("/", response_model=CharacterModel)
async def create_character(
    user: Annotated[UserModel, Depends(get_current_user)],
    char_data: Annotated[CharacterCreate, Body()],
):
    result = await characters_db.create_character(user, char_data.name)
    return result
