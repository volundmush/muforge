import asyncio
import uuid
from datetime import datetime, timezone


class Session:
    __slots__ = (
        "app",
        "user_id",
        "pc_id",
        "user",
        "pc",
        "created_at",
        "last_active_at",
        "subscriptions",
        "active",
    )

    def __init__(self, app, user_id: uuid.UUID, pc_id: uuid.UUID):
        self.app = app
        # The user_id also serves as the session ID.
        self.user_id = user_id
        self.pc_id = pc_id
        # User and PC are filled in after the session is created.
        self.user = None
        self.pc = None
        self.created_at = datetime.now(timezone.utc)
        self.last_active_at = datetime.now(timezone.utc)
        self.subscriptions: list[asyncio.Queue] = []
        self.active = False

    async def send_event(self, event) -> None:
        for q in self.subscriptions:
            await q.put(event)

    def send_event_nowait(self, event) -> None:
        for q in self.subscriptions:
            q.put_nowait(event)

    async def execute_command(self, command: str) -> None | dict:
        self.last_active_at = datetime.now(timezone.utc)
        return await self.pc.execute_command(command)

    def subscribe(self) -> asyncio.Queue:
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
        await self.pc.enter_game()

    async def stop_local(self):
        for q in self.subscriptions:
            await q.put(None)

    async def stop(self, graceful: bool = True):
        if not self.active:
            return
