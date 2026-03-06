import typing
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import muforge
from muforge.game.db import pcs as pcs_db
from muforge.shared.models.pcs import ActiveAs, CharacterCreate, PCModel
from muforge.shared.models.users import UserModel

from .utils import get_acting_character, get_current_user, streaming_list

router = APIRouter()


@router.get("/", response_model=typing.List[PCModel])
async def get_pcs(user: Annotated[UserModel, Depends(get_current_user)]):
    if not user.admin_level > 0:
        raise HTTPException(
            status_code=403, detail="You do not have permission to view all characters."
        )

    stream = pcs_db.list_pcs()

    return streaming_list(stream)


@router.get("/active", response_model=typing.List[PCModel])
async def get_active_pc(user: Annotated[UserModel, Depends(get_current_user)]):
    pass


@router.get("/{pc_id}", response_model=PCModel)
async def get_pc(
    user: Annotated[UserModel, Depends(get_current_user)], pc_id: uuid.UUID
):
    pc = await pcs_db.find_pc_id(pc_id)
    if pc.user_id != user.id and user.admin_level < 1:
        raise HTTPException(
            status_code=403, detail="Player Character does not belong to you."
        )
    return pc


@router.get("/{pc_id}/active", response_model=ActiveAs)
async def get_pc_active_as(
    user: Annotated[UserModel, Depends(get_current_user)], pc_id: uuid.UUID
):
    acting = await get_acting_pc(user, pc_id)
    return acting


@router.get("/{character_id}/events")
async def stream_character_events(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    # We don't use it; but this verifies that user can control character.
    acting = await get_acting_pc(user, character_id)

    started = False
    if not (session := muforge.PC_SESSIONS.get(character_id, None)):
        session_class = muforge.CLASSES["pc_session"]
        session = session_class(acting)
        muforge.PC_SESSIONS[character_id] = session
        started = True

    async def event_generator():
        queue = session.subscribe()
        graceful = False
        try:
            if started:
                await session.start()
            # blocks until a new event
            while item := await queue.get():
                yield f"event: {item.__class__.__name__}\ndata: {item.model_dump_json()}\n\n"
            graceful = True
        finally:
            session.unsubscribe(queue)
            if not session.subscriptions and session.active:
                await session.stop(graceful=graceful)

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
        raise HTTPException(status_code=404, detail="Character entity not found.")

    await session.execute_command(command.command)

    return {"status": "ok"}


@router.post("/", response_model=CharacterModel)
async def create_character(
    user: Annotated[UserModel, Depends(get_current_user)],
    char_data: Annotated[CharacterCreate, Body()],
):
    result = await characters_db.create_character(user, char_data.name)
    return result
