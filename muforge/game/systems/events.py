import asyncio
import uuid

from collections import defaultdict
from datetime import datetime

import muforge

class EventHub:
    def __init__(self):
        self.subscriptions: dict[uuid.UUID, list[asyncio.Queue]] = defaultdict(list)
        self.subscribed_at: dict[uuid.UUID, datetime] = dict()

    def subscribe(self, character_id: uuid.UUID) -> asyncio.Queue:
        """Create a new queue for this character and add it to the subscription list."""
        q = asyncio.Queue()
        if character_id not in self.subscriptions:
            self.subscribed_at[character_id] = datetime.now()
        self.subscriptions[character_id].append(q)
        return q

    def unsubscribe(self, character_id: uuid.UUID, q: asyncio.Queue):
        """Remove the given queue from this character's subscription list."""
        if character_id in self.subscriptions:
            try:
                self.subscriptions[character_id].remove(q)
            except ValueError:
                pass
            # If no more queues remain for this character, remove the key.
            if not self.subscriptions[character_id]:
                del self.subscriptions[character_id]
                del self.subscribed_at[character_id]

    async def send(self, character_id: uuid.UUID, message):
        """Send a message to all subscribers for this character."""
        if character_id in self.subscriptions:
            # iterate a copy to prevent possible mutation during iteration
            for q in self.subscriptions[character_id].copy():
                await q.put(message)

    def send_nowait(self, character_id: uuid.UUID, message):
        if character_id in self.subscriptions:
            for q in self.subscriptions[character_id].copy():
                q.put_nowait(message)

    async def broadcast(self, message):
        """Send a message to all subscribers blindly."""
        for channel_list in self.subscriptions.values():
            for channel in channel_list:
                await channel.put(message)

    def broadcast_nowait(self, message):
        for channel_list in self.subscriptions.values():
            for channel in channel_list:
                channel.put_nowait(message)

    def online(self) -> set[uuid.UUID]:
        """Return a set of all currently online characters."""
        return set(self.subscriptions.keys())

    def connected_at(self) -> dict[uuid.UUID, datetime]:
        return self.subscribed_at.copy()