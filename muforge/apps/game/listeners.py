class TableListener:
    # The tables that this listener cares about.
    tables: list[str] = []

    async def on_update(self, table: str, id):
        pass

    async def on_insert(self, table: str, id):
        pass

    async def on_delete(self, table: str, id):
        pass
