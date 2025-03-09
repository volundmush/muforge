from collections import defaultdict
from .base import Command
from rich.columns import Columns
from mudforge.utils import partial_match


class HelpCommand(Command):
    name = "help"
    help_category = "System"

    async def func(self):
        if not self.args:
            await self.display_full_help()
            return
        await self.display_file(self.args)

    async def display_file(self, file_name: str):
        commands = self.parser.available_commands().values()
        if not (command := partial_match(file_name, commands, key=lambda c: c.name)):
            await self.send_line(f"Command not found: {file_name}")
            return
        await self.send_line(f"Found Command: {command.name}")

    async def display_full_help(self):
        categories = defaultdict(list)
        commands = self.parser.available_commands().values()
        for command in commands:
            categories[command.help_category].append(command)

        category_keys = sorted(categories.keys())

        for key in category_keys:
            commands = categories[key]
            commands.sort(key=lambda cmd: cmd.name)
            cmds = [cmd.name for cmd in commands]
            col = Columns(cmds, title=key, padding=(0, 5))
            await self.send_rich(col)
