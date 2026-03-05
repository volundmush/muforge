import typing
import uuid
from datetime import datetime
from typing import Optional

import pydantic

from .fields import username
from .mixins import SoftDeleteMixin, TimestampMixin


class UserModel(SoftDeleteMixin):
    id: uuid.UUID
    username: username
    admin_level: int
