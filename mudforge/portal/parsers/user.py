import mudforge
from pydantic import ValidationError
from .base import BaseParser
from ..commands.base import CMD_MATCH
from httpx import HTTPStatusError
from mudforge.utils import partial_match
from mudforge.validators import user_rich_text
from rich.markup import MarkupError
from rich.table import Table

from mudforge.game.db.models import ActiveAs, CharacterModel, UserModel


class UserParser(BaseParser):
    """
    Implements the character selection and user management features.
    """

    async def on_start(self):
        await self.handle_look()

    async def handle_help(self, args: str):
        help_table = self.make_table("Command", "Description", title="User Commands")
        help_table.add_row("help", "Displays this help message.")
        help_table.add_row("create <name>", "Creates a new character.")
        help_table.add_row("play <name>", "Selects a character to play.")
        help_table.add_row("delete <name>", "Deletes a character.")
        help_table.add_row("logout", "Logs out of the game.")
        help_table.add_row("look", "Lists all characters.")
        await self.send_rich(help_table)

    async def handle_create(self, args: str):
        if not args:
            await self.send_line("You must supply a name for your character.")
            return
        js_data = {"name": args}
        try:
            character_data = await self.api_call("POST", "/characters", json=js_data)
        except HTTPStatusError as e:
            await self.send_line(f"Error creating character: {e.response.text}")
            return
        character = CharacterModel(**character_data)
        await self.handle_look()
        await self.send_line(f"Character {character.name} created.")

    async def handle_play(self, args: str):
        if not args:
            await self.send_line("You must supply a name for your character.")
            return
        user_id = self.connection.payload.get("sub")
        character_data = await self.api_call("GET", f"/users/{user_id}/characters")
        characters = [CharacterModel(**c) for c in character_data]

        if not (character := partial_match(args, characters, key=lambda c: c.name)):
            await self.send_line("Character not found.")
            return

        active_data = await self.api_call(
            "PATCH", f"/characters/active/{character.id}", json={}
        )

        active = ActiveAs(**active_data)

        from .character import CharacterParser

        parser = CharacterParser(active)
        await self.connection.push_parser(parser)

    async def handle_delete(self, args: str):
        pass

    async def handle_logout(self):
        pass

    async def handle_look(self):
        user_id = self.connection.payload.get("sub")
        character_data = await self.api_call("GET", f"/users/{user_id}/characters")

        characters = [CharacterModel(**c) for c in character_data]

        character_table = self.make_table("Name", "Last Active", title="Characters")
        for character in characters:
            character_table.add_row(character.name, str(character.last_active_at))
        await self.send_rich(character_table)

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
            case "create":
                await self.handle_create(args)
            case "play":
                await self.handle_play(args)
            case "delete":
                await self.handle_play(args)
            case "logout":
                await self.handle_logout()
            case "look":
                await self.handle_look()
            case _:
                await self.send_line("Invalid command. Type 'help' for help.")
