import typing

from muforge.plugin import BasePlugin


class TelnetPlugin(BasePlugin):
    def name(self) -> str:
        return "MuForge Telnet Portal"
    
    def slug(self) -> str:
        return "telnet"

    def version(self) -> str:
        return "0.0.1"
    
    def portal_services(self):
        from .portal_services import TelnetService, TLSTelnetService
        return {"telnet": TelnetService, "telnets": TLSTelnetService}


plugin = TelnetPlugin

__all__ = ["plugin"]
