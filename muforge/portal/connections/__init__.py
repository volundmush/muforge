import asyncio
import re
import time
import typing
from dataclasses import dataclass, field
from datetime import datetime

from httpx import AsyncClient, HTTPStatusError, Limits
from httpx_sse import aconnect_sse
from loguru import logger
from rich.box import ASCII2
from rich.console import Console
from rich.errors import MarkupError
from rich.markup import escape
from rich.table import Table

from .link import (
    ConnectionLink,
    LinkData,
    LinkDisconnect,
    LinkUpdate,
)

_re_event = re.compile(r"event: (.+)\ndata: (.+)\n\n", re.MULTILINE)


class BaseConnection:
    """
    This represents a single player connection, mapping a protocol like telnet to an HTTPX client connection.
    """

    def __init__(self, service, link: ConnectionLink):
        self.service = service
        self.link = link
        self.task_group = None
        self.console = Console(
            color_system="standard",
            file=self,
            record=True,
            width=self.link.info.width,
            height=self.link.info.height,
            emoji=False,
        )
        self.console._color_system = self.link.info.color
        self.parser_stack = list()
        self.client = None
        self.last_active_at = datetime.now()
        self.shutdown_event = asyncio.Event()
        self.shutdown_cause = None

    @property
    def plugin(self):
        return self.service.plugin

    @property
    def app(self):
        return self.service.app

    def get_headers(self) -> dict[str, str]:
        out = dict()
        out["X-Forwarded-For"] = self.link.info.client_address
        return out

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

    def make_table(self, *args, **kwargs) -> Table:
        base_kwargs = {
            "border_style": "magenta",
            "width": self.link.info.width,
            "highlight": True,
        }
        match self.link.info.encoding:
            case "ascii":
                base_kwargs["box"] = ASCII2
                base_kwargs["safe_box"] = True
            case "utf-8":
                pass
        if self.link.info.screen_reader:
            base_kwargs["box"] = None
        base_kwargs.update(kwargs)
        return Table(*args, **base_kwargs)

    def start_tasks(self, tg):
        tg.create_task(self.run_link())

    async def run(self):
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            self.start_tasks(tg)

            await self.shutdown_event.wait()
            logger.info(
                f"Connection {self.session_name} shutting down: {self.shutdown_cause}"
            )
            raise asyncio.CancelledError()

    async def at_capability_change(self, capability: str, value):
        match capability:
            case "color":
                await self.send_line(f"Capability change: {capability} -> {str(value)}")
            case _:
                await self.send_line(f"Capability change: {capability} -> {value}")

        match capability:
            case "color":
                self.console._color_system = value
            case "encoding":
                if value == "utf-8":
                    self.console._emoji = True
                elif value == "ascii":
                    self.console._emoji = False
            case "height":
                self.console.height = value
            case "width":
                self.console.width = value

    async def send_text(self, text: str):
        await self.link.outgoing_queue.put(LinkData(package="Text.ANSI", data=text))

    async def send_rich(self, *args, **kwargs):
        """
        Sends a Rich message to the client.
        """
        out = self.print(*args, **kwargs)
        await self.send_text(out)

    async def send_rich_line(self, *args, **kwargs):
        """
        Sends a Rich message to the client, ensuring it ends with a newline.
        """
        out = self.print(*args, **kwargs)
        if not out.endswith("\r\n"):
            out += "\r\n"
        await self.send_text(out)

    async def send_line(self, text: str):
        if not text.endswith("\r\n"):
            text += "\r\n"
        await self.send_text(text)

    async def push_parser(self, parser):
        """
        Adds a parser to the stack.
        """
        self.parser_stack.append(parser)
        parser.connection = self
        parser.index = len(self.parser_stack) - 1
        await parser.on_start()

    async def pop_parser(self):
        """
        Removes the top parser from the stack.
        """
        if not self.parser_stack:
            return
        parser = self.parser_stack.pop()
        await parser.on_end()
        if self.parser_stack:
            await self.parser_stack[-1].on_resume()
        else:
            self.shutdown_cause = "no_parser"
            self.shutdown_event.set()

    async def at_receive_command(self, cmd: str):
        if not self.parser_stack:
            self.shutdown_cause = "no_parser"
            self.shutdown_event.set()
            return
        parser = self.parser_stack[-1]
        try:
            await parser.handle_command(text)
        except MarkupError as e:
            await self.send_rich(f"[bold red]Error parsing markup:[/] {escape(str(e))}")
        except Exception as e:
            await self.send_rich(
                f"[bold red]An unexpected error occurred:[/] {escape(str(e))}"
            )

    async def at_receive_data(self, package: str, data: typing.Any):
        if not self.parser_stack:
            self.shutdown_cause = "no_parser"
            self.shutdown_event.set()
            return
        parser = self.parser_stack[-1]
        await parser.handle_incoming_data(package, data)

    async def handle_incoming_event(self, data):
        match data:
            case LinkData(package=package, data=data):
                await self.at_receive_data(package, data)
            case LinkUpdate():
                for k, v in data.info.items():
                    await self.at_capability_change(k, v)
            case LinkDisconnect():
                pass
            case _:
                if custom_handler := getattr(data, "custom_handler", None):
                    await custom_handler(self)

    def create_client(self):
        return AsyncClient(
            base_url=self.app.settings["game_url"],
            http2=True,
            limits=Limits(max_connections=10, max_keepalive_connections=10),
            verify=False,
            follow_redirects=True,
        )

    def get_start_parser(self) -> type:
        return self.app.parsers["auth"]

    async def run_link(self):
        parser_class = self.get_start_parser()

        async with self.create_client() as client:
            self.client = client
            await self.push_parser(parser_class())

            while True:
                try:
                    data = await self.link.incoming_queue.get()
                    await self.handle_incoming_event(data)
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error(e)

    async def api_call(
        self,
        method: str,
        path: str,
        *,
        query: dict = None,
        json: dict = None,
        data: dict = None,
        headers: dict[str, str] = None,
    ) -> dict:
        """
        Generic method to call the game server's REST API.

        :param method: HTTP method (e.g., 'GET', 'POST')
        :param path: The endpoint path (e.g., '/boards')
        :param query: Dictionary of query parameters to include in the URL.
        :param json: JSON serializable body (if needed).
        :return: The parsed JSON response.
        :raises HTTPStatusError: For non-200 responses.
        """
        use_headers = self.get_headers()
        if headers:
            use_headers.update(headers)
        try:
            response = await self.client.request(
                method, path, params=query, json=json, data=data, headers=use_headers
            )
            # Raise an exception if the status code indicates an error.
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            logger.error(
                f"HTTP error on {method} {path}: {exc.response.status_code} {exc.response.text}"
            )
            # Optionally, handle the error (for example, re-raise or return a default value)
            raise
        except Exception as exc:
            logger.error(f"Error during API call {method} {path}: {str(exc)}")
            raise

    async def api_stream(
        self,
        method: str,
        path: str,
        *,
        query: dict = None,
        json: dict = None,
        data: dict = None,
        headers: dict[str, str] = None,
    ) -> typing.AsyncGenerator[tuple[str, dict], None]:
        """
        Opens a streaming request to the given endpoint and yields chunks of text.
        For Server-Sent Events (SSE), you'll typically want to parse these chunks
        line-by-line and accumulate complete events.
        """
        use_headers = self.get_headers()
        if headers:
            use_headers.update(headers)
        try:
            async with aconnect_sse(
                self.client,
                method,
                path,
                params=query,
                json=json,
                data=data,
                headers=use_headers,
                timeout=None,
            ) as event_source:
                # Raise an exception for non-2xx status codes.
                async for event in event_source.aiter_sse():
                    yield event.event, event.json()
        except HTTPStatusError as exc:
            # Log or handle errors as needed
            logger.error(
                f"HTTP error: {exc.response.status_code} - {exc.response.text}"
            )
            raise
