import asyncio
import mudpy


class Link:

    def __init__(self, session: "GameSession"):
        self.session = session
        self.queue = asyncio.Queue()

    async def run(self):
        pass
