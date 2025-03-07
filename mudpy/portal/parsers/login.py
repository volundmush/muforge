from .base import BaseParser


class LoginParser(BaseParser):

    async def on_start(self):
        await self.connection.send_line("Welcome to Phantasm!")

    async def handle_command(self, event: str):
        await self.connection.send_line(f"ECHO: {event}")
