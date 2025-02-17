import asyncio
import socketio
import mudpy

class Link:

    def __init__(self, session: "GameSession"):
        self.session = session
        self.sio = None
        # This must contain a tuple of (event: str, data: any/dict)
        self.queue = asyncio.Queue()

    async def run(self):
        async with socketio.AsyncClient() as sio:
            self.sio = sio
            await self.handle_connect()
            await self.on_connect()
            await self.sio.wait()

    async def handle_connect(self):
        await self.sio.connect(mudpy.SETTINGS["PORTAL"]["weburl"])

    async def on_connect(self):
        pass

    async def listen_events(self):
        while True:
            event = await self.sio.receive()
            print(f"Received event: {event}")

    async def push_queue(self):
        while True:
            message = await self.queue.get()
            await self.sio.emit(message[0], message[1])