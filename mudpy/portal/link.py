import asyncio
import mudpy


class Link:

    def __init__(self, session: "GameSession"):
        self.session = session
        self.queue = asyncio.Queue()
        self.task_group = None

    async def setup(self):
        pass

    async def run(self):
        await self.setup()
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            tg.create_task(self.run_link())

    async def run_link(self):
        pass
