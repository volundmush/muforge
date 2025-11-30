from .base import Command
from muforge.shared.events.messages import SayMessage

class Say(Command):
    """
    Say something out loud to those around you.
    
    Usages:
        say <message>
            Say the given message out loud to those around you.
    """
    name = "say"
    help_category = "Communications"

    async def func(self):
        if not (loc := self.enactor.location):
            raise self.Error("You are nowhere. You cannot speak.")
        if not self.args:
            raise self.Error("What do you want to say?")
        message = self.args
        neighbors = loc.contents
        for entity in neighbors:
            await entity.send_event(
                SayMessage(
                    entity_id=self.enactor.id,
                    entity_name=self.enactor.get_display_name(entity),
                    message=message,
                )
            )
