import typing

from muforge.plugin import BasePlugin


class BBS(BasePlugin):
    def name(self) -> str:
        return "MuForge BBS"

    def slug(self) -> str:
        return "bbs"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        from .migrations import version001

        return [("version001", version001)]

    def game_routers_v1(self) -> dict[str, typing.Any]:
        from .router import router as bbs_router

        return {
            "/bbs": bbs_router,
        }

    def game_static(self) -> str | None:
        return "static"

    def game_lockfuncs(self) -> dict[str, typing.Any]:
        return dict()

    def depends(self):
        return [("core", ">=0.0.1")]


__all__ = ["BBS"]
