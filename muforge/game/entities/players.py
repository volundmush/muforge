import uuid
from .characters import Character

class Player(Character):
    entity_type: str = "player"
    entity_indexes: list[str] = ["player", "character"]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)