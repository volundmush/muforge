class BaseParser:

    def __init__(self):
        self.link: "Link" = None

    async def on_start(self):
        pass

    async def on_end(self):
        pass

    async def handle_command(self, event: str):
        pass
