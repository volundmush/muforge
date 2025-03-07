import typing


class Command:
    """
    Base class for commands/actions taken by characters.
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
        Check if the command matches the character's input.

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
    def check_access(cls, character) -> bool:
        """
        Check if the character should have access to the command.

        Args:
            character: The character to check access for.

        Returns:
            bool: True if the character has access, False otherwise.
        """
        return True

    def __init__(self, character, match_cmd, match_data: dict[str, str]):
        self.character = character
        self.match_cmd = match_cmd
        self.match_data = match_data
        self.cmd = match_data.get("cmd", "")
        self.switches = [x.strip() for x in match_data.get("switches", "").split("/")]
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
            self.send_line(f"{err}")

    async def func(self):
        """
        Execute the command.
        """
        pass

    def send_text(self, text: str):
        self.character.send_text(text)

    def send_line(self, text: str):
        self.character.send_line(text)

    @property
    def admin_level(self):
        return self.character.admin_level

    @property
    def true_admin_level(self):
        return self.character.true_admin_level

    @property
    def session(self):
        return self.character.session