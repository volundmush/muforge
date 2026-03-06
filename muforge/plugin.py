import typing


class BasePlugin:
    """
    The base class for all plugins used by MuForge.
    Plugins extend its capabilities.

    methods that begin with game_ are relevant only to the game server.
    Likewise, methods that begin with portal_ are relevant only to the portal server.
    """
    def __init__(self, app):
        self.app = app
    
    def name(self) -> str:
        """
        Returns the name of the plugin. This is just for displaying it in lists.
        """
        raise NotImplementedError

    def version(self) -> str:
        """
        Returns the version of the plugin.
        Should use semantic versioning (e.g. "1.0.0").
        """
        raise NotImplementedError

    def slug(self) -> str:
        """
        Returns the slug of the plugin. This is used for dependencies and should be unique and unchanging.
        Should be lowercase and contain only letters, numbers, and underscores.
        """
        raise NotImplementedError

    def game_migrations(self) -> list[tuple[str, typing.Any]]:
        """
        Returns a list of tuples of (migration_name, migration_module)
        A migration module contains the following properties:

        upgrade, downgrade: either strings (SQL statements) or callables (async functions) that perform the migration.

        depends: a list of tuples of (plugin_slug, migration_name) that this migration depends on.
        The migrations will be run in the order of the dependencies.
        """
        return []

    def depends(self) -> list[tuple[str, str]]:
        """
        Returns a tuple of (plugin_slug, version) tuples that this plugin depends on.
        """
        return []

    def game_routers_v1(self) -> dict[str, typing.Any]:
        """
        Announces the routers for this plugin.
        The dictionary is in [prefix, router] format. routers are fastapi APIRouter objects.
        """
        return dict()

    def game_static(self) -> str | None:
        """
        used by FastAPI's StaticFiles to serve static files for the game server.
        Disabled by returning None. if str, it's the folder name. usually 'static'
        """
        return None

    def game_lockfuncs(self) -> dict[str, typing.Any]:
        """
        Announces lockfuncs for this plugin.
        The dictionary is in [name, func] format. funcs are callables that take a character and return a boolean.
        """
        return dict()
    
    async def pre_setup(self):
        """
        This is called before any dependency checks or exports are done. This might be done for customizing
        what the plugin exports based on what other plugins are present.
        """
        pass

    async def post_setup(self):
        """
        This is called after all dependency checks have been resolved.
        """
        pass