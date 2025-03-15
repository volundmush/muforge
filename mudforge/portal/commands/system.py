from mudforge.utils import partial_match
from .base import Command


class _System(Command):
    help_category = "System"


class Think(_System):
    """
    This command will echo back whatever you type after the command.

    Use it to test text formatting.

    Usage:
        think <text>
    """

    name = "think"
    help_category = "System"
    aliases = {"think": 2, "echo": 3}

    async def func(self):
        if not self.args:
            raise self.Error("Think what?")
        await self.send_rich(self.args)


class Idle(_System):
    """
    This commmand does nothing. Have your client send it on a timer
    if you experience connection issues. It might help.
    
    Unlike most commands, it is case sensitive.

    Usage:
        IDLE
    """
    name = "IDLE"
    # This command is actually handled by a much earlier point than the command
    # parser, so it doesn't need to be usable here.
    unusable = True



class Client(_System):
    """
    Display or reconfigure your client settings. Use this if your MUD client
    doesn't negotiate properly with the server.

    Usages:
        client
            Displays current settings and details.

        client <setting>=<value>
            Sets a new setting.
    
    Settings and Values:
        width = <int>
            The width of the client display. default is 78.
        color = <none|ansi|xterm256|truecolor>
            The color mode for the client. default is ansi.
        encoding = <ascii|utf-8>
            The text encoding for the client. default is ascii.
            Enable utf-8 to see special characters and emojis.
            If your client doesn't support it, you may see garbage.
        screenreader = <on|off>
            Enable or disable screenreader mode. default is off.
            This exchanges visual aesthetics for cleaner text-to-speech.
            Please alert staff if something isn't accessible enough.
    
    Helpful Notes:
        different MUD clients have different quirks and capabilities.
        This game is programmed to work with many, but it prefers those
        that support TTYPE/MTTS, NAWS, xterm256 color, and UTF-8 encoding.
    """

    name = "client"
    aliases = {"client": 2}

    async def func(self):
        if not self.args:
            await self.display_details()
            return
        if not self.lsargs and self.rsargs:
            raise self.Error("Usage: client <setting>=<value>")
        setting, value = self.lsargs, self.rsargs
        choices = {"width", "color", "encoding", "screenreader"}
        choice = partial_match(setting, choices)
        if not choice:
            raise self.Error(f"Invalid setting: {setting}")
        
        if not (f := getattr(self, f"set_{choice}"), None):
            raise self.Error(f"Setting {choice} is not configurable.")
        await f(value)

    async def display_details(self):
        await self.send_line("Client Settings:")
        # Since pydantic models can be printed by rich with auto-coloring,
        # we can just send the model to rich.
        await self.send_rich(self.connection.capabilities)
    
    async def set_width(self, value):
        try:
            width = int(value)
        except ValueError:
            raise self.Error("Width must be an integer.")
        if width < 1:
            raise self.Error("Width must be greater than 0.")
        self.connection.capabilities.width = width
        await self.connection.at_capability_change("width", width)
        await self.send_line(f"Width set to {width}.")
    
    async def set_color(self, value):
        choices = {"none": 0, "ansi": 1, "xterm256": 2, "truecolor": 3}
        choice = partial_match(value, choices.keys())
        if not choice:
            raise self.Error(f"Invalid color mode: {value}")
        # change capabilities here...
        color_type = choices.get(choice)
        self.connection.capabilities.color = color_type
        await self.connection.at_capability_change("color", color_type)
        await self.send_line(f"Color set to {choice}.")
    
    async def set_encoding(self, value):
        choices = {"ascii", "utf-8"}
        choice = partial_match(value, choices)
        if not choice:
            raise self.Error(f"Invalid encoding: {value}")
        # change capabilities here...
        self.connection.capabilities.encoding = choice
        await self.connection.at_capability_change("encoding", choice)
        await self.send_line(f"Encoding set to {choice}.")

    async def set_screenreader(self, value):
        choices = {"on": True, "off": False}
        choice = partial_match(value, choices)
        if not choice:
            raise self.Error(f"Invalid screenreader setting: {value}")
        val = choices.get(choice)
        # change capabilities here...
        self.connection.capabilities.screenreader = val
        await self.connection.at_capability_change("screenreader", val)
        await self.send_line(f"Screenreader mode set to {choice}.")