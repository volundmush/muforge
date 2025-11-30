from .base import Command


class Look(Command):
    name = "look"
    help_category = "Informative"

    async def func(self):
        if not (loc := self.enactor.location):
            raise self.Error("You are nowhere. You cannot look at anything.")
        for field in (loc.name, loc.desc):
            await self.send_line(field)
        
        if not loc.contents:
            return
        await self.send_line("You see:")
        for entity in loc.contents:
            if entity.id != self.enactor.id:
                await self.send_line(f"{entity.render_for_location_view(self.enactor)}")