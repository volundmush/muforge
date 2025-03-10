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




class SystemUpdate(BaseModel):
    admin_level: int
    message: str
