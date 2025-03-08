from .base import Command
from mudforge.game.api.models import ActiveAs
import time


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
            raise self.Error("You must specify a number.")

        level = int(self.args)
        if level > self.enactor.user.admin_level:
            # just error out here. The API won't allow it anyways. No reason to fire off an unnecessary API call.
            raise self.Error(
                "You cannot set your acting admin_level higher than your user admin_level."
            )

        start_time = time.perf_counter()
        active_data = await self.api_call(
            "PATCH",
            f"/characters/active/{self.enactor.character.id}",
            json={"admin_level": level},
        )
        end_time = time.perf_counter()
        active = ActiveAs(**active_data)
        self.enactor = active
        self.parser.active = active

        await self.send_line(f"Your acting admin_level has been set to {level}.")
        await self.send_line(f"Operation took {end_time - start_time:.4f} seconds.")
