import typing


class BasePlugin:
    """
    The base class for all plugins used by MuForge.
    Plugins extend its capabilities.

    methods that begin with game_ are relevant only to the game server.
    Likewise, methods that begin with portal_ are relevant only to the portal server.
    """

    def __init__(self, app, settings=None):
        self.app = app
        self.settings = (
            settings
            if settings is not None
            else app.complete_settings.get("PLUGIN", dict()).get(self.slug(), dict())
        )

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

    def game_lockfuncs(self) -> dict[str, typing.Callable]:
        """
        Announces lockfuncs for this plugin.
        The dictionary is in [name, func] format. funcs are callables that take a character and return a boolean.
        """
        return dict()

    def game_services(self) -> dict[str, type]:
        """
        Announces services for this plugin.
        The dictionary is in [name, service] format. services are callables that take the app and return an object.
        """
        return dict()

    def game_classes(self) -> dict[str, type]:
        """
        Announces classes for this plugin.
        The dictionary is in [name, class] format. classes are callables that take the app and return an object.
        """
        return dict()

    def game_commands(self) -> dict[str, type]:
        """
        Announces commands for this plugin.
        The dictionary is in [name, command] format. commands are callables that take the app and return an object.
        """
        return dict()

    def portal_classes(self) -> dict[str, type]:
        """
        Announces portal classes for this plugin.
        The dictionary is in [name, class] format. classes are callables that take the app and return an object.
        """
        return dict()

    def portal_services(self) -> dict[str, type]:
        """
        Announces services for this plugin.
        The dictionary is in [name, service] format. services are callables that take the app and return an object.
        """
        return dict()

    def portal_parsers(self) -> dict[str, typing.Any]:
        """
        Announces portal parsers for this plugin.
        The dictionary is in [name, parser] format. parsers are callables that take the Connection return an object.
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

    async def setup_final(self):
        """
        This is called when the game has finished loading everything else.
        """
        pass
