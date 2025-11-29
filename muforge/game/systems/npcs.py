import uuid
from .characters import Character

class NPC(Character):
    entity_type: str = "npc"
    entity_indexes: list[str] = ["npc", "character"]
    
    def __init__(self, id: uuid.UUID, name: str):
        super().__init__(id, name)