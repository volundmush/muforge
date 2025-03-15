from collections import defaultdict
from .base import Command
from rich.columns import Columns
from mudforge.utils import partial_match


class Help(Command):
    """
    Displays the help menu. You're looking at it right now!

    Usages:
        help
            Display the full help menu.
        help <topic>
            Display help for a specific topic. Usually these are commands.
    
    Helpful Notes:
        In help files, you will notice sections of text enclosed in <> and [].
        [] means this section is optional, while <> means it's a placeholder
        for required data. You don't actually type the enclosures.

        The proper syntax of this command is:
            help[ <topic>]

        Because you can either use it standalone or provide a topic.

        Like this:
            help
            help think
    """
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
        await command.display_help(self.parser)

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
        await self.send_line(f"""Type 'help help' for more information.""")