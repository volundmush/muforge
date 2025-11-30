from muforge.shared.commands import Command as BaseCommand

from muforge.shared.events.messages import Text, Line

class Command(BaseCommand):

    def __init__(self, match_cmd, match_data: dict[str, str], enactor):
        super().__init__(match_cmd, match_data)
        self.enactor = enactor

    async def send_text(self, text: str):
        await self.enactor.send_event(Text(message=text))

    async def send_line(self, text: str):
        await self.enactor.send_event(Line(message=text))
    
    async def send_event(self, event):
        await self.enactor.send_event(event)