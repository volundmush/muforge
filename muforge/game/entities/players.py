import uuid
import muforge
from .characters import Character

class Player(Character):
    entity_type: str = "player"
    entity_indexes: list[str] = ["player", "character"]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)

    async def enter_game(self) -> None:
        # Placeholder for any initialization logic when the player enters the game
        if not self.location:
            eot = muforge.LOCATIONS["end_of_time"]
            await self.move_to(eot)
            await self.execute_command("look")