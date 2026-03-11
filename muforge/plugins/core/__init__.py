import typing

from muforge.plugin import BasePlugin


class Core(BasePlugin):
    def __init__(self, app, settings=None):
        super().__init__(app, settings)
        self.crypt_context = None

    def name(self) -> str:
        return "MuForge Core"

    def slug(self) -> str:
        return "core"

    def version(self) -> str:
        return "0.0.1"

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        from .migrations import version001

        return [("version001", version001)]

    def game_routers_v1(self) -> dict[str, typing.Any]:
        from .routers.auth import router as auth_router
        from .routers.pcs import router as pcs_router
        from .routers.users import router as users_router

        return {
            "/auth": auth_router,
            "/users": users_router,
            "/pcs": pcs_router,
        }

    def game_static(self) -> str | None:
        return "static"

    def game_lockfuncs(self) -> dict[str, typing.Any]:
        return dict()

    def portal_parsers(self):
        from .portal_parsers.auth import LoginParser
        from .portal_parsers.character import CharacterParser
        from .portal_parsers.user import UserParser

        return {"auth": LoginParser, "user": UserParser, "character": CharacterParser}

    def portal_services(self) -> dict[str, type]:
        from .portal_services.connection import ConnectionService

        return {"connection": ConnectionService}

    async def post_setup(self):
        from passlib.context import CryptContext

        self.crypt_context = CryptContext(**self.settings.get("crypt", {}))


__all__ = ["Core"]
