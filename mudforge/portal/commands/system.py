from .base import Command


class Think(Command):
    name = "think"
    help_category = "System"
    aliases = {"think": 2, "echo": 3}

    async def func(self):
        if not self.args:
            raise self.Error("Think what?")
        await self.send_rich(self.args)
