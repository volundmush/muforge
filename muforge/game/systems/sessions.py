import weakref
import uuid
import muforge
from datetime import datetime, timezone

class Session:

    def __init__(self, pc: "PlayerCharacter"):
        self.pc = pc
        self.puppet = pc
        self.created_at = datetime.now(timezone.utc)
        self.last_active_at = datetime.now(timezone.utc)
        self.command_queue: list[str] = list()
    
    async def send_event(self, event) -> None:
        await muforge.EVENT_HUB.send(self.pc.id, event)

    def is_switched(self) -> bool:
        return self.pc is not self.puppet
    
    async def execute_command(self, command: str) -> None:
        pass