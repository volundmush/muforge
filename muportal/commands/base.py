import typing
import re

from muforge.shared.commands import Command as BaseCommand


class Command(BaseCommand):

    def __init__(self, match_cmd, match_data: dict[str, str], parser):
        super().__init__(match_cmd, match_data)
        self.parser = parser
        self.enactor = parser.active

    @classmethod
    async def display_help(cls, parser: "Parser"):
        """
        Display the help for the command.

        By default this just sends the docstring of the class.
        """
        await parser.send_line(cls.__doc__)


    async def send_text(self, text: str):
        await self.parser.send_text(text)

    async def send_rich(self, *args, **kwargs):
        await self.parser.send_rich(*args, **kwargs)

    async def send_gmcp(self, command: str, data: dict):
        await self.parser.send_gmcp(command, data)

    async def api_call(self, *args, **kwargs):
        return await self.parser.api_call(*args, **kwargs)

    async def api_character_call(self, *args, **kwargs):
        return await self.parser.api_character_call(*args, **kwargs)

    def make_table(self, *args, **kwargs):
        return self.parser.make_table(*args, **kwargs)

    @property
    def connection(self):
        return self.parser.connection

    @property
    def admin_level(self):
        return self.enactor.admin_level

    @property
    def true_admin_level(self):
        return self.enactor.user.admin_level
