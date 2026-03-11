import asyncio
from uuid import UUID

from muforge.application import Service
from muforge.apps.portal.connections import BaseConnection
from muforge.apps.portal.connections.link import ConnectionLink


class ConnectionService(Service):
    def __init__(self, app, plugin):
        super().__init__(app, plugin)
        self.connections: dict[UUID, BaseConnection] = dict()

        self.pending_links = asyncio.Queue()

    async def handle_connection(self, link: ConnectionLink):
        conn = BaseConnection(self, link)
        self.connections[link.info.connection_id] = conn
        await conn.run()
        del self.connections[link.info.connection_id]

    async def run(self):
        while link := await self.pending_links.get():
            asyncio.create_task(self.handle_connection(link))
