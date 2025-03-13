import datetime
from pydantic import BaseModel, Field
from .base import EventBase


class SystemPing(EventBase):
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

    async def handle_event(self, conn: "BaseConnection"):
        pass
