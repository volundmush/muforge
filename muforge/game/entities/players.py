import uuid
import muforge
from datetime import datetime, timezone
from .characters import Character
from muforge.shared.models.characters import CharacterModel

class Player(Character):
    entity_type: str = "player"
    entity_indexes: list[str] = ["player", "character"]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)
        self.user_id: uuid.UUID = kwargs.get("user_id")
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
        self.deleted_at = kwargs.get("deleted_at", None)
        self.last_active_at = kwargs.get("last_active_at", datetime.now(timezone.utc))

    async def enter_game(self) -> None:
        # Placeholder for any initialization logic when the player enters the game
        if not self.location:
            eot = muforge.LOCATIONS["end_of_time"]
            await self.move_to(eot)
            await self.execute_command("look")
        await self.send_line("Welcome to the game! Type 'help' for a list of commands.")
    
    def to_model(self) -> CharacterModel:
        data = {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "last_active_at": self.last_active_at
        }
        return CharacterModel(**data)