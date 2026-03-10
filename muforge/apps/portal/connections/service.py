from muforge.application import Service
from uuid import UUID
import muforge
from .connection import Connection
from .link import ConnectionLink
import asyncio

class ConnectionService(Service):
    
    def __init__(self, app):
        super().__init__(app)
        self.connections: dict[UUID, Connection] = dict()

        self.pending_links = asyncio.Queue()
    
    async def handle_connection(self, link: ConnectionLink):
        l = Connection(self, link)
        self.connections[link.info.connection_id] = l
        await l.run()
        del self.connections[link.info.connection_id]

    async def run(self):
        while True:
            if link := await self.pending_links.get():
                asyncio.create_task(self.handle_connection(link))