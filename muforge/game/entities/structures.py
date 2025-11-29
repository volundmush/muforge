import uuid
from ..entities.base import BaseEntity
from .mixins import HasLocation, HasInventory, HasEquipment

class Structure(BaseEntity, HasLocation, HasInventory, HasEquipment):
    entity_type: str = "structure"
    entity_family: str = "structures"
    entity_indexes: list[str] = ["structure",]
    
    def __init__(self, id: uuid.UUID, name: str, **kwargs):
        super().__init__(id, name, **kwargs)
        HasLocation.__init__(self)
        HasInventory.__init__(self)
        HasEquipment.__init__(self)