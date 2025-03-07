from .base import Command

class ALevelCommand(Command):
    """
    Command used to change acting admin_level.

    Usage:
        alevel <level>
    
    Example:
        alevel 5
    
    The level cannot exceed your user admin_level.

    Admin Levels:
        0: Player
        1: Helper
        2: Builder
        3: Admin
        4: Owner
        5: Superuser / Developer
    """
    name = "alevel"

    async def func(self):
        if not self.args.isdigit():
            await self.error("You must specify a number.")
            return
        level = int(self.args)
        if level > self.enactor.user.admin_level:
            # just error out here. The API won't allow it anyways. No reason to fire off an unnecessary API call.
            raise self.Error("You cannot set your acting admin_level higher than your user admin_level.")