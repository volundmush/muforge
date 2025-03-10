import pydantic
import typing
import uuid
from datetime import datetime, timedelta, timezone
from mudforge.game.lockhandler import LockHandler


from pydantic import BaseModel
from typing import Annotated, Optional


class UserModel(BaseModel):
    id: uuid.UUID
    email: pydantic.EmailStr
    email_confirmed_at: Optional[datetime]
    display_name: Optional[str]
    admin_level: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class CharacterModel(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime
    last_active_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class ActiveAs(BaseModel):
    user: UserModel
    character: CharacterModel


class BoardModel(BaseModel, LockHandler):
    board_key: str
    name: str
    description: Optional[str]
    anonymous_name: Optional[str]
    faction_id: Optional[int]
    board_order: int
    created_at: datetime
    updated_at: datetime
    lock_data: dict[str, str]


class PostModel(BaseModel):
    post_key: str
    title: str
    body: str
    created_at: datetime
    modified_at: datetime
    spoofed_name: str
    character_id: typing.Optional[int] = None
    character_name: typing.Optional[str] = None


class FactionModel(BaseModel, LockHandler):
    id: int
    name: str
    abbreviation: str
    created_at: datetime
    updated_at: datetime
    description: Optional[str]
    category: str
    private: bool
    hidden: bool
    can_leave: bool
    kick_rank: int
    start_rank: int
    title_self: bool
    member_permissions: set[str]
    public_permissions: set[str]
    lock_data: dict[str, str]


class SystemUpdate(BaseModel):
    admin_level: int
    message: str
