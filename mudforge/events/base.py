import pydantic
from pydantic import Field
import datetime


class EventBase(pydantic.BaseModel):
    """
    Base class for all events.
    """

    async def handle_event(self, conn: "BaseConnection"):
        happened_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
