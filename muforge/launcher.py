class Launcher:
    def __init__(self, settings):
        self.settings = settings

    async def run(self):
        print(self.settings)
