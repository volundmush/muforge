import asyncio
import typing
from uuid import UUID
from dataclasses import dataclass, field

from rich.color import ColorType

@dataclass(slots=True)
class ClientInfo:
    """
    A dataclass that holds the capabilities of the client. This is updated as negotiations occur and statuses change.
    It can be subclassed to add more fields as needed, if you need to implement more TelnetOption subtypes that aren't
    covered here.
    """
    connection_id: UUID
    client_name: str = "UNKNOWN"
    client_version: str = "UNKNOWN"
    client_protocol: str = "UNKNOWN"
    client_address: str = "UNKNOWN"
    client_hostname: str = "UNKNOWN"
    tls: bool = False
    encoding: str = "ascii"
    color: ColorType = ColorType.DEFAULT
    width: int = 78
    height: int = 24
    gmcp: bool = False
    mssp: bool = False
    screen_reader: bool = False


@dataclass(slots=True)
class LinkUpdate:
    info: dict[str, typing.Any]


@dataclass(slots=True)
class LinkDisconnect:
    reason: str


@dataclass(slots=True)
class LinkText:
    text: str


@dataclass(slots=True)
class LinkGMCP:
    package: str
    data: dict


@dataclass(slots=True)
class LinkMSSP:
    data: tuple[tuple[str, str], ...]


class ConnectionLink:
    """
    A ConnectionLink 
    """
    
    def __init__(self):
        self.info = ClientInfo()
        self.incoming_queue = asyncio.Queue()
        self.outgoing_queue = asyncio.Queue()