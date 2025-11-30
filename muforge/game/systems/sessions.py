import weakref
import uuid
import muforge
import asyncio
from datetime import datetime, timezone

class Session:

    def __init__(self, pc: "PlayerCharacter", hub):
        self.pc = pc
        self.puppet = pc
        self.hub = hub
        self.created_at = datetime.now(timezone.utc)
        self.last_active_at = datetime.now(timezone.utc)
    
    async def send_event(self, event) -> None:
        await self.hub.send(self.pc.id, event)

    def active_character(self):
        return self.puppet if self.is_switched() else self.pc

    def is_switched(self) -> bool:
        return self.pc is not self.puppet
    
    async def execute_command(self, command: str) -> None:
        target = self.active_character()
        self.last_active_at = datetime.now(timezone.utc)
        await target.execute_command(command)