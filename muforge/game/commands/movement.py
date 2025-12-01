from .base import Command
import muforge
from muforge.shared.utils import partial_match

class Go(Command):
    name = "go"
    help_category = "Movement"

    async def func(self):
        if not self.args:
            await self.send_line("Usage: go <direction>")
            return
        
        if not (loc := self.enactor.location):
            await self.send_line("You are nowhere. You cannot go anywhere.")
            return
        
        if not loc.exits:
            await self.send_line("There are no exits here.")
            return
        
        if not (choice := partial_match(self.args.lower(), loc.exits.keys())):
            await self.send_line("You can't go that way.")
            return

        new_loc = muforge.LOCATIONS[loc.exits[choice]]
        # Here you would add the logic to move the character in the specified direction.
        await self.send_line(f"You go {choice}.")
        await self.enactor.move_to(new_loc)
