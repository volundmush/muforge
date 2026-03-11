from rich.errors import MarkupError


class BaseParser:
    def __init__(self):
        self.connection: "BaseConnection" = None
        self.index: int = 0

    async def on_start(self):
        pass

    async def on_end(self):
        pass

    async def on_resume(self):
        await self.on_start()

    async def handle_incoming_data(self, package: str, data: typing.Any):
        match package:
            case "Text.Command":
                await self.handle_command(data)
            case _:
                pass

    async def execute_command(self, event: str):
        pass

    async def handle_command(self, event: str):
        try:
            await self.execute_command(event)
        except MarkupError as e:
            await self.send_rich(f"[bold red]Error parsing markup:[/] {escape(str(e))}")
        except Exception as e:
            await self.send_rich(
                f"[bold red]An unexpected error occurred:[/] {escape(str(e))}"
            )

    async def send_text(self, text: str):
        await self.connection.send_text(text)

    async def send_line(self, text: str):
        await self.connection.send_line(text)

    async def send_rich(self, *args, **kwargs):
        await self.connection.send_rich(*args, **kwargs)

    async def send_gmcp(self, command: str, data: dict):
        await self.connection.send_gmcp(command, data)

    async def api_call(self, *args, **kwargs):
        return await self.connection.api_call(*args, **kwargs)

    async def api_stream(self, *args, **kwargs):
        return await self.connection.api_stream(*args, **kwargs)

    def make_table(self, *args, **kwargs):
        return self.connection.make_table(*args, **kwargs)
