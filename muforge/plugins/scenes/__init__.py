import typing

from muforge.plugin import BasePlugin


class ScenesPlugin(BasePlugin):
    def name(self) -> str:
        return "MuForge Scene System"
    
    def slug(self) -> str:
        return "scenes"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        from .migrations import version001

        return [("version001", version001)]

    def game_routers_v1(self) -> dict[str, typing.Any]:
        from .routers.scene import router as scene_router
        from .routers.plots import router as plots_router

        return {
            "/plots": plots_router,
            "/scenes": scene_router,
        }
    
    def game_static(self) -> str | None:
        return "static"
    
    def game_lockfuncs(self) -> dict[str, typing.Any]:
        return dict()
    
    def depends(self):
        return [("core", ">=0.0.1")]


plugin = ScenesPlugin

__all__ = ["plugin"]
