import pydantic
import uuid
import datetime

from .base import EventBase


class CharacterCreated(EventBase):
    user_id: uuid.UUID
    user_name: str
    character_id: uuid.UUID
    character_name: str
    happened_at: datetime.datetime = datetime.datetime.now()

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(
            f"Character {self.character_name} created for {self.user_name}."
        )


class CharacterDeleted(CharacterCreated):

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_text(
            f"Character {self.character_name} deleted for {self.user_name}."
        )
