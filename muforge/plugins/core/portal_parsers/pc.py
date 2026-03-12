import asyncio
import uuid

from httpx import HTTPStatusError
from loguru import logger
from rich.errors import MarkupError
from rich.markup import escape

from muforge.apps.portal.connections.parser import BaseParser

from ..db.pcs import PCModel
from ..db.users import UserModel


class PCParser(BaseParser):
    def __init__(self, user: UserModel, character: PCModel):
        super().__init__()
        self.user = user
        self.character = character
        self.shutdown_event = asyncio.Event()
        self.client = None
        self.stream_task = None
        self.sid = None

    async def on_start(self):
        await self.send_line(f"You have entered the game as {self.character.name}.")
        self.stream_task = self.connection.task_group.create_task(self.stream_updates())

    async def on_end(self):
        self.shutdown_event.set()

    async def handle_event(self, event_name: str, event_data: dict):

        if event_class := self.app.events.get(event_name, None):
            event = event_class(**event_data)
            await event.handle_event(self)
        else:
            logger.error(f"Unknown event: {event_name}")

    async def stream_updates(self):
        disconnects: int = 0
        while True:
            try:
                if disconnects > 0:
                    await asyncio.sleep(2 ^ disconnects)
                async for event_name, event_data in self.connection.api_stream(
                    "GET", f"/v1/pcs/{self.character.id}/events"
                ):
                    disconnects = 0
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
                disconnects += 1
                return
            except Exception as e:
                logger.exception("Unknown error occurred in stream_updates.")
                await self.send_line("An error occurred. Please contact staff.")
                disconnects += 1
                return

    async def handle_command(self, event: str):
        try:
            result = await self.api_call(
                "POST",
                f"/v1/pcs/{self.self.character.id}/command",
                json={"command": event},
            )
        except MarkupError as e:
            await self.send_rich(f"[bold red]Error parsing markup:[/] {escape(str(e))}")
        except ValueError as error:
            await self.send_line(f"{error}")
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.send_line("You have been disconnected.")
                await self.connection.pop_parser()
                return
            logger.exception("HTTP error in handle_command: %s")
            await self.send_line("An error occurred. Please contact staff.")
        except Exception as error:
            await self.send_line(f"An error occurred: {error}")
            logger.exception(error)
