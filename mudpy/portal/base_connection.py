import mudpy
import asyncio

from httpx import AsyncClient
from loguru import logger
from rich.console import Console

from dataclasses import dataclass, field

from rich.color import ColorType


@dataclass(slots=True)
class Capabilities:
    session_name: str = ""
    encryption: bool = False
    client_name: str = "UNKNOWN"
    client_version: str = "UNKNOWN"
    host_address: str = "UNKNOWN"
    host_port: int = -1
    host_names: list[str, ...] = None
    encoding: str = "ascii"
    color: ColorType = ColorType.DEFAULT
    width: int = 78
    height: int = 24
    mccp2: bool = False
    mccp2_enabled: bool = False
    mccp3: bool = False
    mccp3_enabled: bool = False
    gmcp: bool = False
    msdp: bool = False
    mssp: bool = False
    mslp: bool = False
    mtts: bool = False
    naws: bool = False
    sga: bool = False
    linemode: bool = False
    force_endline: bool = False
    screen_reader: bool = False
    mouse_tracking: bool = False
    vt100: bool = False
    osc_color_palette: bool = False
    proxy: bool = False
    mnes: bool = False

    def display_client_name(self):
        if self.client_version != "UNKNOWN":
            return f"{self.client_name} (v {self.client_version})"
        return self.client_name


@dataclass(slots=True)
class ClientHello:
    userdata: dict[str, "Any"] = field(default_factory=dict)
    capabilities: Capabilities = field(default_factory=Capabilities)


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


class BaseConnection:
    """
    Base implementation of the glue between the Portal and the Game. This represents a single player connection, mapping
    a protocol like telnet to a SurrealDB client connection.
    """

    def __init__(self):
        self.capabilities = Capabilities()
        self.task_group = None
        self.user_input_queue = asyncio.Queue()
        self.console = Console(
            color_system="standard",
            file=self,
            record=True,
            width=self.capabilities.width,
            height=self.capabilities.height,
        )
        self.console._color_system = self.capabilities.color
        self.parser_stack = list()
        self.headers: dict[str, str] = {
            "X-Forwarded-For": self.capabilities.host_address
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
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            await self.setup()

    async def change_capabilities(self, changed: dict[str, "Any"]):
        for attr, value in changed.items():
            setattr(self.capabilities, attr, value)
            await self.at_capability_change(attr, value)

    async def at_capability_change(self, capability: str, value):
        match capability:
            case "color":
                self.console._color_system = value

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
                data = await self.user_input_queue.get()
                await self.handle_user_input(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(e)
