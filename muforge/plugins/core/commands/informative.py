from .base import Command
import muforge

class Look(Command):
    name = "look"
    help_category = "Informative"

    async def func(self):
        if not (loc := self.enactor.location):
            raise self.Error("You are nowhere. You cannot look at anything.")
        for field in (loc.name, loc.desc):
            await self.send_line(field)
        
        if (neighbors := loc.get_neighbors(self.enactor)):
            await self.send_line("You see:")
            for entity in neighbors:
                if entity.id != self.enactor.id:
                    await self.send_line(f"{entity.render_for_location_view(self.enactor)}")
        
        if loc.exits:
            await self.send_line("Exits:")
            for k, v in loc.exits.items():
                await self.send_line(f"- {k} to '{muforge.LOCATIONS.get(v, None)}'")
        

class Inventory(Command):
    name = "inventory"
    help_category = "Informative"

    async def func(self):
        if not (contents := self.enactor.get_inventory()):
            raise self.Error("Your inventory is empty.")
        await self.send_line("You are carrying:")
        for item in contents:
            await self.send_line(f"- {item.render_for_inventory_view(self.enactor)}")


class Equipment(Command):
    name = "equipment"
    help_category = "Informative"

    async def func(self):
        if not (equipment := self.enactor.get_equipment()):
            raise self.Error("You have no equipment equipped.")
        await self.send_line("You're using the following equipment:")
        for slot, item in equipment.items():
            await self.send_line(f"{slot.capitalize()}: {item.render_for_inventory_view(self.enactor)}")