import pydantic
from pydantic import Field
import datetime


class EventBase(pydantic.BaseModel):
    happened_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    """
    Base class for all events.
    """

    async def handle_event(self, conn: "BaseConnection"):
        pass

    async def handle_event_parser(self, parser: "BaseParser"):
        pass
