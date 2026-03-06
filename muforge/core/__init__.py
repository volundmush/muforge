import typing

from muforge.plugin import BasePlugin


class CorePlugin(BasePlugin):
    def slug(self) -> str:
        return "core"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        from .migrations import version001

        return [("version001", version001)]

    def game_routers(self) -> dict[str, typing.Any]:
        from .routers.auth import router as auth_router
        from .routers.pcs import router as pcs_router
        from .routers.users import router as users_router

        return {
            "/auth": auth_router,
            "/users": users_router,
            "/pcs": pcs_router,
        }


plugin = CorePlugin

__all__ = ["plugin"]
