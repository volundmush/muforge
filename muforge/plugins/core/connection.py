import jwt
import time
import asyncio
import muforge
from httpx import HTTPStatusError
from muforge.apps.portal.connections.connection import BaseConnection

from .routers.auth import TokenResponse

class CoreConnection(BaseConnection):
    """
    The Core Connection adds JWT functionality but not much more.
    """

    def __init__(self, service, link):
        super().__init__(service, link)
        self.jwt = None
        self.payload = None
        self.refresh_token = None

    def get_headers(self) -> dict:
        out = super().get_headers()
        if self.jwt:
            out["Authorization"] = f"Bearer {self.jwt}"
        return out
    
    async def handle_token(self, token: TokenResponse):
        self.jwt = token.access_token
        self.payload = jwt.decode(self.jwt, options={"verify_signature": False})
        self.refresh_token = token.refresh_token

    async def handle_login(self, token: TokenResponse):
        await self.handle_token(token)
        parser_class = muforge.CLASSES["user_parser"]

        up = parser_class()
        await self.push_parser(up)

    def start_tasks(self, tg):
        super().start_tasks(tg)
        tg.create_task(self.run_refresher())
    
    async def run_refresher(self):
        while True:
            try:
                await asyncio.sleep(60)
                if not self.jwt:
                    continue
                # the expiry is stored as a unix timestamp... let's check how much, if any, time is left
                remaining = self.payload["exp"] - time.time()

                if remaining <= 0:
                    # this is bad. we somehow missed the expiry time.
                    # we should probably log this and then cancel the connection.
                    await self.send_line(
                        "Your session has expired. Please log in again."
                    )
                    self.shutdown_cause = "session_expired"
                    self.shutdown_event.set()
                    return

                # if we have at least 5 minutes left, sleep until only 5 minutes are left
                if remaining > 300:
                    await asyncio.sleep(remaining - 300)

                # now we have 5 minutes or less left. let's refresh the token.
                try:
                    json_data = await self.api_call(
                        "POST",
                        "/auth/refresh",
                        json={"refresh_token": self.refresh_token},
                    )
                except HTTPStatusError as e:
                    await self.send_line(
                        "Your session has expired. Please log in again."
                    )
                    self.shutdown_cause = "session_expired"
                    self.shutdown_event.set()
                    return
                token = TokenResponse(**json_data)
                await self.handle_token(token)

            except asyncio.CancelledError:
                return