import weakref
import uuid

from pydantic import BaseModel

from .base import BaseEntity
from .mixins import HasLocation, HasEquipment, HasInventory


class AttributeSchema(BaseModel):
    id: str
    name: str
    desc: str = ""
    base: int = 0
    max: int = 0


class Character(BaseEntity, HasLocation, HasInventory, HasEquipment):
    entity_type: str = "character"
    entity_family: str = "characters"
    entity_indexes: list[str] = ["character",]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)
        HasLocation.__init__(self)
        HasInventory.__init__(self)
        HasEquipment.__init__(self)
        self.health = kwargs.get("health", 100)
        self.max_health = kwargs.get("max_health", 100)
        self.xp = kwargs.get("xp", 0)
        self.level = kwargs.get("level", 1)
        self.xp_to_next = kwargs.get("xp_to_next", 50)
        self.credits = kwargs.get("credits", 0)
        self.unlocked_locations = kwargs.get("unlocked_locations", [])
    
    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "xp": self.xp,
            "level": self.level,
            "xp_to_next": self.xp_to_next,
            "credits": self.credits
        }
        if self.location:
            data["location"] = self.location.id
        return data