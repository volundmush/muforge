class Service:
    load_priority: int = 0
    start_priority: int = 0

    def is_valid(self):
        return True

    async def setup(self):
        pass

    async def run(self):
        pass

    def shutdown(self):
        pass