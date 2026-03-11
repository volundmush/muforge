import typing

from muforge.plugin import BasePlugin


class Telnet(BasePlugin):
    def __init__(self, app, settings=None):
        super().__init__(app, settings)
        self.telnet_options = dict()

    def name(self) -> str:
        return "MuForge Telnet Portal"

    def slug(self) -> str:
        return "telnet"

    def version(self) -> str:
        return "0.0.1"

    def portal_services(self):
        from .portal_services import TelnetService, TLSTelnetService

        return {"telnet": TelnetService, "telnets": TLSTelnetService}

    def portal_classes(self) -> dict[str, type]:
        from .protocol import MudTelnetProtocol

        return {"mud_telnet_protocol": MudTelnetProtocol}

    def portal_telnet_options(self) -> dict[str, type]:
        from .protocol.options import (
            CHARSETOption,
            EOROption,
            GMCPOption,
            LineModeOption,
            MCCP2Option,
            MCCP3Option,
            MSSPOption,
            MTTSOption,
            NAWSOption,
            SGAOption,
        )

        return {
            "sga": SGAOption,
            "naws": NAWSOption,
            "charset": CHARSETOption,
            "eor": EOROption,
            "gmcp": GMCPOption,
            "linemode": LineModeOption,
            "mccp2": MCCP2Option,
            "mccp3": MCCP3Option,
            "mssp": MSSPOption,
            "mtts": MTTSOption,
        }

    async def post_setup(self):
        for p in self.app.plugin_load_order:
            if hasattr(p, "portal_telnet_options"):
                self.telnet_options.update(p.portal_telnet_options())


__all__ = ["Telnet"]
