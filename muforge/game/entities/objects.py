import uuid
from .base import BaseEntity
from .mixins import HasLocation, HasEquipment, HasInventory

class Object(BaseEntity, HasLocation, HasInventory, HasEquipment):
    entity_type: str = "object"
    entity_family: str = "objects"
    entity_indexes: list[str] = ["object",]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)
        HasLocation.__init__(self)
        HasInventory.__init__(self)
        HasEquipment.__init__(self)