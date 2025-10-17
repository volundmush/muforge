import pydantic
from typing import Optional
import uuid
from datetime import datetime

from .mixins import TimestampMixin, SoftDeleteMixin
from .users import UserModel
from .fields import name_line

class CharacterModel(SoftDeleteMixin):
    id: uuid.UUID
    user_id: uuid.UUID
    name: name_line
    created_at: datetime
    last_active_at: datetime


class ActiveAs(pydantic.BaseModel):
    user: UserModel
    character: CharacterModel

class CharacterCreate(pydantic.BaseModel):
    name: str