import uuid
import muforge
import typing
from loguru import logger

from muforge.shared.commands import CMD_MATCH

class BaseEntity:
    entity_type: str = None
    entity_family: str = None
    entity_indexes: list[str] = list()
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        self.id = id
        self.name = name
        self.session: "None | GameSession" = None

    def get_display_name(self, viewer: "Character") -> str:
        return self.name
    
    def get_search_keywords(self) -> list[str]:
        return self.name.lower().split()
    
    def render_description(self, viewer: "Character") -> str:
        return f"{self.get_display_name(viewer)} (an entity of type {self.entity_type})"
    
    def render_for_location_view(self, viewer: "Character") -> str:
        return self.get_display_name(viewer)
    
    def render_for_inventory_view(self, viewer: "Character") -> str:
        return self.get_display_name(viewer)
    
    def _save_base(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "entity_family": self.entity_family,
            "entity_class": f"{self.__class__.__module__}:{self.__class__.__name__}",
        }
    
    def save_data(self) -> dict:
        return dict()

    def export_save(self) -> dict:
        base = self._save_base()
        base["data"] = self.save_data()
        return base
    
    def get_admin_level(self, ignore_quell: bool = False) -> int:
        if self.session and self.session.user:
            return self.session.user.admin_level
        return 0

    def available_commands(self) -> dict[int, list["Command"]]:
        out = dict()
        for priority, commands in muforge.GAME_COMMANDS_PRIORITY.items():
            for c in commands:
                if c.check_access(self):
                    out[c.name] = c
        return out

    def iter_commands(self):
        priorities = sorted(muforge.GAME_COMMANDS_PRIORITY.keys())
        for priority in priorities:
            for command in muforge.GAME_COMMANDS_PRIORITY[priority]:
                if command.check_access(self):
                    yield command

    def match_command(self, cmd: str) -> typing.Optional["Command"]:
        for command in self.iter_commands():
            if command.unusable:
                continue
            if command.check_match(self, cmd):
                return command
    
    async def execute_command(self, event: str) -> dict:

        try:
            if not (match_data := CMD_MATCH.match(event)):
                raise ValueError(f"Huh? (Type 'help' for help)")
            # regex match_data.groupdict() returns a dictionary of all the named groups
            # and their values. Missing groups are None. That's silly. We'll filter it out.
            match_dict = {
                k: v for k, v in match_data.groupdict().items() if v is not None
            }
            cmd_key = match_dict.get("cmd")
            if not (cmd := self.match_command(cmd_key.lower())):
                raise ValueError(f"Huh? (Type 'help' for help)")
            command = cmd(self, cmd_key, match_dict)
            result = await command.execute()
            return result or {"ok": True}
        except ValueError as error:
            await self.send_line(f"{error}")
            return {"ok": False, "error": str(error)}
        except Exception as error:
            if self.get_admin_level() >= 1:
                await self.send_line(f"An error occurred: {error}")
            else:
                await self.send_line(f"An unknown error occurred. Contact staff.")
            logger.exception(error)
            return {"ok": False, "error": str(error)}
    
    async def send_line(self, text: str):
        if self.session:
            await self.session.send_line(text)
    
    async def send_text(self, text: str):
        if self.session:
            await self.session.send_text(text)
    
    async def send_event(self, event) -> None:
        if self.session:
            await self.session.send_event(event)
    
    def register_entity(self):
        muforge.ENTITIES[self.id] = self
        for idx in self.entity_indexes:
            muforge.ENTITY_TYPE_INDEX[idx].add(self)
    
    def unregister_entity(self):
        if self.id in muforge.ENTITIES:
            del muforge.ENTITIES[self.id]
        for idx in self.entity_indexes:
            if self in muforge.ENTITY_TYPE_INDEX[idx]:
                muforge.ENTITY_TYPE_INDEX[idx].remove(self)