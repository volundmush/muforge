import typing
import re

CMD_MATCH = re.compile(
    r"(?s)^(?P<cmd>\S+?)(?:/(?P<switches>\S+)?)?(?P<fullargs> +(?P<args>(?P<lsargs>.+?)(?:=(?P<rsargs>.*))?)?)?$"
)


class Command:
    """
    Help not implemented for this command. Contact staff!
    """

    name = "!NOTSET!"
    help_category = "Uncategorized"
    priority = 0
    aliases = dict()
    min_level = 0
    # Set this to true if you want the command to exist but never reach the parser.
    # this could be helpful for creating help files or meta-topics.
    unusable = False

    class Error(Exception):
        pass

    @classmethod
    def check_match(cls, enactor: "ActingAs", command: str) -> typing.Optional[str]:
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

    def __init__(self, match_cmd, match_data: dict[str, str]):
        self.match_cmd = match_cmd
        self.match_data = match_data
        self.cmd = match_data.get("cmd", "")
        self.switches = [x.strip() for x in match_data.get("switches", "").split("/")]
        self.fullargs = match_data.get("fullargs", "")
        self.args = match_data.get("args", "")
        self.lsargs = match_data.get("lsargs", "").strip()
        self.rsargs = match_data.get("rsargs", "").strip()
        self.args_array = self.args.split()
        

    def can_execute(self) -> bool:
        """
        Check if the command can be executed.
        """
        return True

    async def execute(self):
        """
        Execute the command.
        """
        if not self.can_execute():
            return
        try:
            await self.func()
        except self.Error as err:
            await self.send_line(f"{err}")

    async def func(self):
        """
        Execute the command.
        """
        pass

    async def send_text(self, text: str):
        pass

    async def send_line(self, text: str):
        await self.send_text(text + "\r\n" if not text.endswith("\r\n") else text)
