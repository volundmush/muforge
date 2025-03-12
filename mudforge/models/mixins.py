from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class SoftDeleteMixin(TimestampMixin):
    deleted_at: Optional[datetime]