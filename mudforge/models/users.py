import pydantic
from typing import Optional
import uuid
from datetime import datetime

from .mixins import TimestampMixin, SoftDeleteMixin
from .fields import optional_name_line

class UserModel(SoftDeleteMixin):
    id: uuid.UUID
    email: pydantic.EmailStr
    email_confirmed_at: Optional[datetime]
    display_name: optional_name_line
    admin_level: int

