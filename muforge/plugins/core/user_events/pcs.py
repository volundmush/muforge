import uuid
import datetime

import pydantic

from muforge.events import EventBase


class CorePCCreated(EventBase):
    user_id: uuid.UUID
    user_name: str
    pc_id: uuid.UUID
    pc_name: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(
            f"Player Character {self.pc_name} created for user: {self.user_name}."
        )


class CorePCDeleted(CorePCCreated):

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(
            f"Player Character {self.pc_name} deleted from user: {self.user_name}."
        )


class CorePCRenamed(EventBase):
    user_id: uuid.UUID
    user_name: str
    pc_id: uuid.UUID
    old_pc_name: str
    new_pc_name: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(
            f"Player Character {self.old_pc_name} renamed to {self.new_pc_name} for user: {self.user_name}."
        )