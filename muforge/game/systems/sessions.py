import weakref
import uuid
import muforge
import asyncio
from datetime import datetime, timezone

class Session:

    def __init__(self, pc: "PlayerCharacter"):
        self.pc = pc
        self.player = pc
        self.puppet = pc
        self.created_at = datetime.now(timezone.utc)
        self.last_active_at = datetime.now(timezone.utc)
        self.subscriptions: list[asyncio.Queue] = []
        self.active = True

        self.node = None
        self.combat = None
        self.unclaimed_loot = list()

    async def send_event(self, event) -> None:
        for q in self.subscriptions:
            await q.put(event)

    def send_event_nowait(self, event) -> None:
        for q in self.subscriptions:
            q.put_nowait(event)

    def is_switched(self) -> bool:
        return self.puppet is not self.pc
    
    async def execute_command(self, command: str) -> None | dict:
        self.last_active_at = datetime.now(timezone.utc)
        return await self.puppet.execute_command(command)
    
    def subscribe(self, character_id: uuid.UUID) -> asyncio.Queue:
        """Create a new queue for this character and add it to the subscription list."""
        q = asyncio.Queue()
        self.subscriptions.append(q)
        return q
    
    def unsubscribe(self, q: asyncio.Queue):
        """Remove the given queue from this session's subscription list."""
        try:
            self.subscriptions.remove(q)
        except ValueError:
            pass
    
    async def start(self):
        """
        Start the session. Should do login things.

        """
        self.active = True

    async def stop_local(self):
        for q in self.subscriptions:
            await q.put(None)

    async def stop(self, graceful: bool = True):
        if not self.active:
            return