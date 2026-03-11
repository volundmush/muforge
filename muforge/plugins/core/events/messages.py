import uuid
import datetime
import pydantic
from rich.columns import Columns
from rich.console import Group

from muforge.portal.base_connection import BaseConnection

from muforge.events import EventBase

class CoreText(EventBase):
    entity_id: uuid.UUID | None = None
    entity_name: str | None = None
    message: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(self.message)

class CoreLine(CoreText):

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_line(self.message)

class SayMessage(EventBase):
    entity_id: uuid.UUID
    entity_name: str
    message: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_line(
            f"{self.entity_name} says, \"{self.message}\""
        )

class ColumnMessage(EventBase):
    padding_min: int = 0
    padding_max: int = 5
    data: list[tuple[str, list[str]]] = pydantic.Field(default_factory=list)

    async def handle_event(self, conn: "BaseConnection"):
        cols = list()
        for title, items in self.data:
            col = Columns(items, title=title, padding=(self.padding_min, self.padding_max), expand=True)
            cols.append(col)
        await conn.send_rich(Group(*cols))