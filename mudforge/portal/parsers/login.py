import mudforge
from pydantic import ValidationError
from .base import BaseParser
from ..commands.base import CMD_MATCH
from httpx import HTTPStatusError
from mudforge.utils import validate_rich
from rich.markup import MarkupError
from rich.table import Table

from mudforge.game.api.auth import (
    UserLogin,
    TokenResponse,
    CharacterLogin,
    CharacterTokenResponse,
)


class LoginParser(BaseParser):
    """
    Implements the login menu. User registration and authentication, etc.
    """

    async def show_welcome(self):
        # TODO: Figure out a welcome screen solution.
        await self.send_line(f"Welcome to {mudforge.SETTINGS['SHARED']['name']}!")

    async def on_start(self):
        await self.show_welcome()

    async def handle_help(self, args: str):
        help_table = self.make_table("Command", "Description", title="Help")
        help_table.add_row("help", "Show this help message.")
        help_table.add_row("login <email>=<password>", "Login to the game.")
        help_table.add_row("register <email>=<password>", "Register a new account.")
        # help_table.add_row("play <character>=<password>", "Login to a character.")
        help_table.add_row("quit", "Quit the game.")
        help_table.add_row("look", "Show the welcome screen.")
        await self.send_rich(help_table)

    async def handle_login(self, lsargs: str, rsargs: str):
        if not lsargs and rsargs:
            await self.send_line("Usage: login <email>=<password>")
            return
        try:
            u = UserLogin(email=lsargs, password=rsargs)
        except ValidationError as e:
            await self.send_line(f"Invalid login credentials: {e}")
            return
        # this uses the /auth/register endpoint... which should give us a TokenResponse.

        data = {"username": u.email, "password": u.password, "grant_type": "password"}
        try:
            json_data = await self.api_call("POST", "/auth/login", data=data)
        except HTTPStatusError as e:
            await self.send_line(f"Login failed: {e}")
            return
        token = TokenResponse(**json_data)
        await self.connection.handle_login(token)

    async def handle_register(self, lsargs: str, rsargs: str):
        if not lsargs and rsargs:
            await self.send_line("Usage: register <email>=<password>")
            return
        try:
            u = UserLogin(email=lsargs, password=rsargs)
        except ValidationError as e:
            await self.send_line(f"Invalid registration credentials: {e}")
            return

        try:
            data = u.model_dump()
            json_data = await self.api_call("POST", "/auth/register", data=data)
        except HTTPStatusError as e:
            await self.send_line(f"Registration failed: {e}")
            return
        token = TokenResponse(**json_data)
        await self.connection.handle_login(token)

    async def handle_play(self, lsargs: str, rsargs: str):
        await self.send_line("Play handling goes here.")

    async def handle_quit(self):
        await self.send_line("Goodbye!")
        self.connection.shutdown_cause = "quit"
        self.connection.shutdown_event.set()

    async def handle_rich(self, args: str):
        await self.send_line(f"Provided to Rich: {args}")
        processed = validate_rich(args)
        await self.send_rich(processed)

    async def handle_command(self, event: str):
        matched = CMD_MATCH.match(event)
        if not matched:
            await self.send_line("Invalid command. Type 'help' for help.")
            return
        match_dict = {k: v for k, v in matched.groupdict().items() if v is not None}
        cmd = match_dict.get("cmd", "")
        args = match_dict.get("args", "")
        lsargs = match_dict.get("lsargs", "")
        rsargs = match_dict.get("rsargs", "")
        match cmd.lower():
            case "help":
                await self.handle_help(args)
            case "login":
                await self.handle_login(lsargs, rsargs)
            case "register":
                await self.handle_register(lsargs, rsargs)
            case "play":
                await self.handle_play(lsargs, rsargs)
            case "quit":
                await self.handle_quit()
            case "look":
                await self.show_welcome()
            case "rich":
                await self.handle_rich(args)
            case _:
                await self.send_line("Invalid command. Type 'help' for help.")
