import pydantic


class EventBase(pydantic.BaseModel):
    """
    Base class for all events.
    """

    async def handle_event(self, conn: "BaseConnection"):
        pass
