from muforge.application import BaseApplication


class Application(BaseApplication):
    name = "portal"

    def __init__(self, settings):
        super().__init__(settings)
        self.parsers: dict[str, type] = dict()

    async def setup_parsers(self):
        for p in self.plugin_load_order:
            self.parsers.update(p.portal_parsers())

    async def setup(self):
        await super().setup()
