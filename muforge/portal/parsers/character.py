import typing
import muforge
import asyncio
from socketio.async_client import AsyncClient
from loguru import logger
from httpx import HTTPStatusError

from rich.markup import escape, MarkupError

from muforge.shared.models.characters import ActiveAs

from .base import BaseParser
from ..commands.base import CMD_MATCH


class CharacterParser(BaseParser):

    def __init__(self, active: ActiveAs):
        super().__init__()
        self.active = active
        self.sio = None
        self.shutdown_event = asyncio.Event()
        self.client = None
        self.stream_task = None
        self.sid = None

    async def on_start(self):
        await self.send_line(
            f"You have entered the game as {self.active.character.name}."
        )
        self.stream_task = self.connection.task_group.create_task(self.run_socketio())

    async def on_end(self):
        self.shutdown_event.set()


    async def handle_event(self, event_name: str, event_data: dict):

        if event_class := mudforge.EVENTS.get(event_name, None):
            event = event_class(**event_data)
            await event.handle_event(self)
        else:
            logger.error(f"Unknown event: {event_name}")

    async def stream_updates(self):
        while True:
            try:
                async for event_name, event_data in self.connection.api_stream(
                    "GET", f"/characters/{self.active.character.id}/events"
                ):
                    await self.handle_event(event_name, event_data)
                self.stream_task.cancel()
                await self.connection.pop_parser()
            except asyncio.CancelledError:
                return
            except HTTPStatusError as e:
                if e.response.status_code == 401:
                    await self.send_line("You have been disconnected.")
                    return
                logger.exception("HTTP error in stream_updates: %s")
                await self.send_line("An error occurred. Please contact staff.")
                return
            except Exception as e:
                logger.exception("Unknown error occurred in stream_updates.")
                await self.send_line("An error occurred. Please contact staff.")
                return

    def available_commands(self) -> dict[0, list["Command"]]:
        out = dict()
        for priority, commands in muforge.COMMANDS_PRIORITY.items():
            for c in commands:
                if c.check_access(self.active):
                    out[c.name] = c
        return out

    def iter_commands(self):
        priorities = sorted(muforge.COMMANDS_PRIORITY.keys())
        for priority in priorities:
            for command in muforge.COMMANDS_PRIORITY[priority]:
                if command.check_access(self.active):
                    yield command

    def match_command(self, cmd: str) -> typing.Optional["Command"]:
        for command in self.iter_commands():
            if command.unusable:
                continue
            if command.check_match(self.active, cmd):
                return command

    async def refresh_active(self):
        json_data = await self.api_call(
            "GET", f"/characters/{self.active.character.id}/active"
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
            if self.active.user.admin_level >= 1:
                await self.send_line(f"An error occurred: {error}")
            else:
                await self.send_line(f"An unknown error occurred. Contact staff.")
            logger.exception(error)

    async def api_character_call(self, *args, **kwargs):
        if "query" not in kwargs:
            kwargs["query"] = dict()
        kwargs["query"]["character_id"] = self.active.character.id
        return await self.connection.api_call(*args, **kwargs)
