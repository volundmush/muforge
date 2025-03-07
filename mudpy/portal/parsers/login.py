import mudpy
from .base import BaseParser
from ..commands.base import CMD_MATCH



class LoginParser(BaseParser):

    async def show_welcome(self):
        await self.send_line(f"Welcome to {mudpy.SETTINGS['SHARED']['name']}!")

    async def on_start(self):
        await self.show_welcome()

    async def handle_help(self, args: str):
        await self.send_line("Help text goes here.")
    
    async def handle_login(self, lsargs: str, rsargs: str):
        await self.send_line("Login handling goes here.")
    
    async def handle_register(self, lsargs: str, rsargs: str):
        await self.send_line("Register handling goes here.")
    
    async def handle_play(self, lsargs: str, rsargs: str):
        await self.send_line("Play handling goes here.")

    async def handle_quit(self):
        await self.send_line("Goodbye!")
        self.connection.shutdown()

    async def handle_command(self, event: str):
        matched = CMD_MATCH.match(event)
        if not matched:
            await self.send_line("Invalid command. Type 'help' for help.")
            return
        cmd = matched.group("cmd")
        args = matched.group("args")
        lsargs = matched.group("lsargs")
        rsargs = matched.group("rsargs")
        if "=" not in args:
            await self.send_line("Invalid command. Type 'help' for help.")
            return
        match cmd.lower():
            case "help":
                await self.handle_help(args)
            case "login":
                await self.handle_login(lsargs, rsargs)
            case "register":
                await self.handle_register(lsargs, rsargs)
            case "play":
                await self.handle_play(lsargs, rsargs)
            case "quit":
                await self.handle_quit()
            case "look":
                await self.show_welcome()
            case _:
                await self.send_line("Invalid command. Type 'help' for help.")