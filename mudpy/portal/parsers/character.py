import typing
import mudpy
from mudpy.game.api.models import ActiveAs
from loguru import logger

from rich.markup import escape, MarkupError

from .base import BaseParser
from ..commands.base import CMD_MATCH


class CharacterParser(BaseParser):

    def __init__(self, active: ActiveAs):
        super().__init__()
        self.active = active

    async def on_start(self):
        pass

    def available_commands(self) -> dict[0, list["Command"]]:
        out = dict()
        for priority, commands in mudpy.COMMANDS_PRIORITY.items():
            for c in commands:
                if c.check_access(self.active):
                    out[c.name] = c
        return out

    def iter_commands(self):
        priorities = sorted(mudpy.COMMANDS_PRIORITY.keys())
        for priority in priorities:
            for command in mudpy.COMMANDS_PRIORITY[priority]:
                if command.check_access(self.active):
                    yield command

    def match_command(self, cmd: str) -> typing.Optional["Command"]:
        for command in self.iter_commands():
            if command.check_match(self.active, cmd):
                return command

    async def refresh_active(self):
        json_data = await self.api_call(
            "GET",
            "/characters/active/me",
            query={"character_id": self.active.character.id},
        )
        self.active = ActiveAs(**json_data)

    async def handle_command(self, cmd: str):
        try:
            await self.refresh_active()
        except Exception as e:
            logger.error(e)
            await self.send_line("An error occurred. Please contact staff.")
            return

        try:
            if not (match_data := CMD_MATCH.match(cmd)):
                raise ValueError(f"Huh? (Type 'help' for help)")
            # regex match_data.groupdict() returns a dictionary of all the named groups
            # and their values. Missing groups are None. That's silly. We'll filter it out.
            match_dict = {
                k: v for k, v in match_data.groupdict().items() if v is not None
            }
            cmd_key = match_dict.get("cmd")
            if not (cmd := self.match_command(cmd_key.lower())):
                raise ValueError(f"Huh? (Type 'help' for help)")
            command = cmd(self, cmd_key, match_dict)
            await command.execute()
        except MarkupError as e:
            await self.send_rich(f"[bold red]Error parsing markup:[/] {escape(str(e))}")
        except ValueError as error:
            await self.send_line(f"{error}")
        except Exception as error:
            if self.active.admin_level >= 1:
                await self.send_line(f"An error occurred: {error}")
            else:
                await self.send_line(f"An unknown error occurred. Contact staff.")
            logger.exception(error)
