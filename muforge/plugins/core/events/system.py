from muforge.events import EventBase


class SystemPing(EventBase):
    async def handle_event(self, conn: "BaseConnection"):
        pass
