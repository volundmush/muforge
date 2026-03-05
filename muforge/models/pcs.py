import uuid
from datetime import datetime
from typing import Optional

import pydantic

from .fields import pc_name
from .mixins import SoftDeleteMixin, TimestampMixin
from .users import UserModel


class PCModel(SoftDeleteMixin):
    id: uuid.UUID
    user_id: uuid.UUID
    name: pc_name


class CharacterCreate(pydantic.BaseModel):
    name: pc_name
