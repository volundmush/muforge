import uuid
import muforge

async def create_entity(
        class_name: str,
        name: str,
        **data,
    ) -> "BaseEntity":
        entity_id = uuid.uuid4()
        entity_class = muforge.ENTITY_CLASSES.get(class_name)
        entity = entity_class(id=entity_id, name=name, **data)
        muforge.ENTITY_REGISTRY.register(entity)
        return entity