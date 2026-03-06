import typing

from muforge.plugin import BasePlugin


class FactionsPlugin(BasePlugin):
    def name(self) -> str:
        return "MuForge Factions"
    
    def slug(self) -> str:
        return "factions"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        from .migrations import version001

        return [("version001", version001)]

    def game_routers_v1(self) -> dict[str, typing.Any]:
        from .router import router as fac_router

        return {
            "/factions": factions_router,
        }
    
    def game_static(self) -> str | None:
        return "static"
    
    def game_lockfuncs(self) -> dict[str, typing.Any]:
        return dict()
    
    def depends(self):
        return [("org", ">=0.0.1")]


plugin = FactionsPlugin

__all__ = ["plugin"]
