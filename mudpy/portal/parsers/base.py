class BaseParser:

    def __init__(self):
        self.connection: "BaseConnection" = None

    async def on_start(self):
        pass

    async def on_end(self):
        pass

    async def handle_command(self, event: str):
        pass

    async def send_text(self, text: str):
        await self.connection.send_text(text)
    
    async def send_line(self, text: str):
        await self.connection.send_line(text)
    
    async def send_rich(self, *args, **kwargs):
        await self.connection.send_rich(*args, **kwargs)
    
    async def send_gmcp(self, command: str, data: dict):
        await self.connection.send_gmcp(command, data)