import weakref
import uuid

from pydantic import BaseModel

from .entities import BaseEntity
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
    
    def __init__(self, id: uuid.UUID, name: str):
        super().__init__(id, name)
        HasLocation.__init__(self)
        HasInventory.__init__(self)
        HasEquipment.__init__(self)
        self.session: "None | CharacterSession" = None