import typing
import re

CMD_MATCH = re.compile(
    r"(?s)^(?P<cmd>\S+?)(?:/(?P<switches>\S+)?)?(?P<fullargs> +(?P<args>(?P<lsargs>.+?)(?:=(?P<rsargs>.*))?)?)?$"
)

class Command:
    """
    Base class for commands/actions taken by users.
    """
    name = "!NOTSET!"
    priority = 0
    aliases = dict()
    min_level = 0
    
    class Error(Exception):
        pass

    @classmethod
    def check_match(cls, command: str) -> typing.Optional[str]:
        """
        Check if the command matches the user's input.

        Command will already be trimmed and lowercase. Equal to the <cmd> in the regex.

        We are a match if it is a direct match with an alias, or if it is a complete match
        with the command name, or if it is a partial match with the command name starting
        with min_length and not contradicting the name.

        IE: "north" should respond to "nort" but not "norb"
        """
        if command == cls.name:
            return cls.name
        for k, v in cls.aliases.items():
            if command == k:
                return k
            if len(command) >= v and command.startswith(k):
                return k
        return None

    @classmethod
    def check_access(cls, enactor: "ActingAs") -> bool:
        """
        Check if the user should have access to the command.

        Args:
            enactor: The user to check access for.

        Returns:
            bool: True if the user has access, False otherwise.
        """
        return True

    def __init__(self, parser, enactor: "ActingAs", match_cmd, match_data: dict[str, str]):
        self.parser = parser
        self.enactor = enactor
        self.match_cmd = match_cmd
        self.match_data = match_data
        self.cmd = match_data.get("cmd", "")
        self.switches = [x.strip() for x in match_data.get("switches", "").split("/")]
        self.fullargs = match_data.get("fullargs", "")
        self.args = match_data.get("args", "")
        self.lsargs = match_data.get("lsargs", "").strip()
        self.rsargs = match_data.get("rsargs", "").strip()
        self.args_array = self.args.split()

    async def can_execute(self) -> bool:
        """
        Check if the command can be executed.
        """
        return True

    async def execute(self):
        """
        Execute the command.
        """
        if not await self.can_execute():
            return
        try:
            await self.func()
        except self.Error as err:
            self.send_line(f"{err}")
        except Exception as e:
            self.send_line(f"An unexpected error occurred: {e}")

    async def func(self):
        """
        Execute the command.
        """
        pass

    async def send_text(self, text: str):
        await self.parser.send_text(text)

    async def send_line(self, text: str):
        await self.parser.send_line(text)
    
    async def send_rich(self, *args, **kwargs):
        await self.parser.send_rich(*args, **kwargs)
    
    async def send_gmcp(self, command: str, data: dict):
        await self.parser.send_gmcp(command, data)

    @property
    def connection(self):
        return self.parser.connection

    @property
    def admin_level(self):
        return self.enactor.admin_level

    @property
    def true_admin_level(self):
        return self.enactor.user.admin_level