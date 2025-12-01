import pydantic
from typing import Optional
import typing
import uuid
from datetime import datetime

from .mixins import TimestampMixin, SoftDeleteMixin
from .fields import optional_name_line

class UserModel(SoftDeleteMixin):
    id: uuid.UUID
    email: pydantic.EmailStr
    email_confirmed_at: Optional[datetime]
    password: pydantic.SecretStr
    display_name: optional_name_line
    admin_level: int

    characters: dict[uuid.UUID, typing.Any] = pydantic.Field(default_factory=dict, exclude=True)  # Placeholder for CharacterModel list
    sessions: dict[uuid.UUID, typing.Any] = pydantic.Field(default_factory=dict, exclude=True)  # Placeholder for SessionModel dict