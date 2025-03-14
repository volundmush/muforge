import mudforge
import asyncio
import jwt
import typing
import time
from datetime import datetime
from httpx import AsyncClient, HTTPStatusError, Limits
from loguru import logger
from rich.console import Console
from rich.markup import MarkupError, escape
from rich.table import Table
from rich.box import ASCII2
from httpx_sse import aconnect_sse
import re
from rich.color import ColorType
from mudforge.models.characters import ActiveAs
from mudforge.models.auth import TokenResponse
from aiomudtelnet import MudClientCapabilities

from dataclasses import dataclass, field

_re_event = re.compile(r"event: (.+)\ndata: (.+)\n\n", re.MULTILINE)


@dataclass(slots=True)
class ClientHello:
    userdata: dict[str, "Any"] = field(default_factory=dict)
    capabilities: MudClientCapabilities = field(default_factory=MudClientCapabilities)


@dataclass(slots=True)
class ClientCommand:
    text: str = ""


@dataclass(slots=True)
class ClientUpdate:
    capabilities: dict[str, "Any"] = field(default_factory=dict)


@dataclass(slots=True)
class ClientDisconnect:
    pass


@dataclass(slots=True)
class ClientGMCP:
    package: str
    data: dict


def color_num_to_rich(color_num: int) -> ColorType:
    match color_num:
        case 0:
            return ColorType.DEFAULT
        case 1:
            return ColorType.STANDARD
        case 2:
            return ColorType.EIGHT_BIT
        case 3:
            return ColorType.TRUECOLOR
        case 4:
            return ColorType.WINDOWS


class BaseConnection:
    """
    Base implementation of the glue between the Portal and the Game. This represents a single player connection, mapping
    a protocol like telnet to a SurrealDB client connection.
    """

    def __init__(self):
        self.session_name = None
        self.host_names = list()
        self.host_port = None
        self.host_address = None
        self.capabilities = MudClientCapabilities()
        self.task_group = None
        self.user_input_queue = asyncio.Queue()
        self.console = Console(
            color_system="standard",
            file=self,
            record=True,
            width=self.capabilities.width,
            height=self.capabilities.height,
            emoji=False,
        )
        self.console._color_system = color_num_to_rich(self.capabilities.color)
        self.parser_stack = list()
        self.client = None
        self.jwt = None
        self.payload: dict[str, "Any"] = dict()
        self.last_active_at = datetime.now()
        self.refresh_token = None
        self.shutdown_event = asyncio.Event()
        self.shutdown_cause = None

    def get_headers(self) -> dict[str, str]:
        out = dict()
        out["X-Forwarded-For"] = self.host_address
        if self.jwt:
            out["Authorization"] = f"Bearer {self.jwt}"
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
            "width": self.capabilities.width,
            "highlight": True,
        }
        match self.capabilities.encoding:
            case "ascii":
                base_kwargs["box"] = ASCII2
            case "utf-8":
                pass
        if self.capabilities.screen_reader:
            base_kwargs["box"] = None
        base_kwargs.update(kwargs)
        return Table(*args, **base_kwargs)

    async def setup(self):
        pass

    async def run(self):
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            tg.create_task(self.run_refresher())
            await self.setup()

            await self.shutdown_event.wait()
            logger.info(
                f"Connection {self.session_name} shutting down: {self.shutdown_cause}"
            )
            raise asyncio.CancelledError()

    color_types = {
        0: "none",
        1: "ansi16",
        2: "xterm256",
        3: "truecolor",
        4: "windows",
    }

    async def at_capability_change(self, capability: str, value):
        match capability:
            case "color":
                await self.send_line(
                    f"Capability change: {capability} -> {self.color_types[value]}"
                )
            case _:
                await self.send_line(f"Capability change: {capability} -> {value}")

        match capability:
            case "color":
                self.console._color_system = color_num_to_rich(value)
            case "encoding":
                if value == "utf-8":
                    self.console._emoji = True
            case "height":
                self.console.height = value
            case "width":
                self.console.width = value

    async def send_text(self, text: str):
        raise NotImplementedError

    async def send_gmcp(self, command: str, data: dict):
        raise NotImplementedError

    async def send_mssp(self, data: dict[str, str]):
        raise NotImplementedError

    async def send_rich(self, *args, **kwargs):
        """
        Sends a Rich message to the client.
        """
        out = self.print(*args, **kwargs)
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

    async def at_receive_line(self, text: str):
        if text != "IDLE":
            await self.user_input_queue.put(ClientCommand(text))

    async def at_receive_gmcp(self, command: str, data: dict):
        await self.user_input_queue.put(ClientGMCP(command, data))

    async def at_receive_command(self, byte: int):
        pass

    async def handle_user_input(self, data):
        match data:
            case ClientCommand():
                if not self.parser_stack:
                    return
                parser = self.parser_stack[-1]
                try:
                    await parser.handle_command(data.text)
                except MarkupError as e:
                    await self.send_rich(
                        f"[bold red]Error parsing markup:[/] {escape(str(e))}"
                    )
                except Exception as e:
                    await self.send_rich(
                        f"[bold red]An unexpected error occurred:[/] {escape(str(e))}"
                    )
            case ClientUpdate():
                pass
            case ClientDisconnect():
                pass
            case ClientGMCP():
                pass

    async def gather_mssp(self) -> dict:
        base_mssp = mudforge.SETTINGS["MSSP"].copy()
        live_mssp = await self.api_call("GET", "/misc/mssp")
        base_mssp.update(live_mssp)
        return base_mssp

    async def distribute_mssp(self):
        if not self.capabilities.mssp:
            return

    def create_client(self):
        return AsyncClient(
            base_url=mudforge.SETTINGS["PORTAL"]["networking"]["game_url"],
            http2=True,
            limits=Limits(max_connections=10, max_keepalive_connections=10),
            verify=False,
            follow_redirects=True,
        )

    async def run_link(self):
        from .parsers.login import LoginParser

        async with self.create_client() as client:
            self.client = client
            await self.push_parser(LoginParser())
            await self.distribute_mssp()

            while True:
                try:
                    data = await self.user_input_queue.get()
                    await self.handle_user_input(data)
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error(e)

    async def handle_token(self, token: TokenResponse):
        self.jwt = token.access_token
        self.payload = jwt.decode(self.jwt, options={"verify_signature": False})
        self.refresh_token = token.refresh_token

    async def handle_login(self, token: TokenResponse):
        await self.handle_token(token)
        from .parsers.user import UserParser

        up = UserParser()
        await self.push_parser(up)

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
                method,
                path,
                params=query,
                json=json,
                data=data,
                headers=use_headers,
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
