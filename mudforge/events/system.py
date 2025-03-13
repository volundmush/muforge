import datetime
from pydantic import BaseModel, Field
from .base import EventBase


class SystemPing(EventBase):

    async def handle_event(self, conn: "BaseConnection"):
        pass
