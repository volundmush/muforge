import asyncio
from httpx import AsyncClient
from loguru import logger
from rich.console import Console

import mudpy

from mudpy.portal.game_session import (
    ClientCommand,
    ClientUpdate,
    ClientDisconnect,
    ClientGMCP,
)


class Link:

    def __init__(self, session: "GameSession"):
        self.session = session
        self.queue = asyncio.Queue()
        self.task_group = None
        self.console = Console(
            color_system="standard",
            file=self,
            record=True,
            width=self.session.capabilities.width,
            height=self.session.capabilities.height,
        )
        self.console._color_system = self.session.capabilities.color
        self.parser_stack = list()
        self.headers: dict[str, str] = {
            "X-Forwarded-For": self.session.capabilities.host_address
        }
        self.client = AsyncClient(
            base_url=mudpy.SETTINGS["PORTAL"]["networking"]["game_url"],
            http2=True,
            headers=self.headers,
        )
        self.jwt = None
        self.refresh_token = None

    def flush(self):
        """
        Used for compatability.
        """

    def write(self, data):
        """
        Used for compatability.
        """

    def print(self, *args, **kwargs) -> str:
        """
        A thin wrapper around Rich.Console's print. Returns the exported data.
        """
        new_kwargs = {"highlight": False}
        new_kwargs.update(kwargs)
        new_kwargs["end"] = "\r\n"
        new_kwargs["crop"] = False
        self.console.print(*args, **new_kwargs)
        return self.console.export_text(clear=True, styles=True)

    async def setup(self):
        pass

    async def run(self):
        await self.setup()
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            await self.run_link()

    async def send_rich(self, *args, **kwargs):
        """
        Sends a Rich message to the client.
        """
        out = self.print(*args, **kwargs)
        await self.session.handle_send_text(out)

    async def send_text(self, text: str):
        """
        Sends plain text to the client.
        """
        await self.session.handle_send_text(text)

    async def send_line(self, text: str):
        if not text.endswith("\r\n"):
            text += "\r\n"
        await self.send_text(text)

    async def push_parser(self, parser):
        """
        Adds a parser to the stack.
        """
        self.parser_stack.append(parser)
        parser.link = self
        await parser.on_start()

    async def pop_parser(self):
        """
        Removes the top parser from the stack.
        """
        if not self.parser_stack:
            return
        parser = self.parser_stack.pop()
        await parser.on_end()

    async def handle_user_input(self, data):
        match data:
            case ClientCommand():
                if not self.parser_stack:
                    return
                parser = self.parser_stack[-1]
                await parser.handle_command(data.text)
            case ClientUpdate():
                pass
            case ClientDisconnect():
                pass
            case ClientGMCP():
                pass

    async def run_link(self):
        from .parsers.login import LoginParser

        await self.push_parser(LoginParser())

        while True:
            try:
                data = await self.session.user_input_queue.get()
                await self.handle_user_input(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(e)
