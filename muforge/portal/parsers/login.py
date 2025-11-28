import muforge
from pydantic import ValidationError
from .base import BaseParser
from muforge.shared.commands import CMD_MATCH
from httpx import HTTPStatusError
from muforge.shared.models.validators import user_rich_text

from muforge.shared.models.auth import UserLogin, TokenResponse


class LoginParser(BaseParser):
    """
    Implements the login menu. User registration and authentication, etc.
    """

    async def show_welcome(self):
        # TODO: Figure out a welcome screen solution.
        await self.send_line(f"Welcome to {muforge.SETTINGS['MSSP']['NAME']}!")
        help_table = self.make_table("Command", "Description")
        help_table.add_row("register <email>=<password>", "Register a new account.")
        help_table.add_row("login <email>=<password>", "Login to an existing account.")
        help_table.add_row("info", "Display game information. (Same as MSSP)")
        help_table.add_row("quit", "Disconnect from the game.")
        await self.send_rich(help_table)

    async def on_start(self):
        await self.show_welcome()

    async def handle_help(self, args: str):
        help_table = self.make_table("Command", "Description", title="Help")
        help_table.add_row("register <email>=<password>", "Register a new account.")
        help_table.add_row("login <email>=<password>", "Login to an existing account.")
        help_table.add_row("info", "Display game information. (Same as MSSP)")
        help_table.add_row("quit", "Disconnect from the game.")
        await self.send_rich(help_table)

    async def handle_info(self):
        data = await self.connection.gather_mssp()
        rendered = "\r\n".join([f"{k}: {v}" for k, v in data.items()])
        await self.send_line(rendered)

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

        data = {
            "username": u.email,
            "password": u.password.get_secret_value(),
            "grant_type": "password",
        }
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
            json_data = await self.api_call("POST", "/auth/register", json=data)
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
        processed = user_rich_text(args)
        await self.send_rich(processed)

    async def handle_command(self, event: str):
        if not (matched := CMD_MATCH.match(event)):
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
            case "info":
                await self.handle_info()
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
