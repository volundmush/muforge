import uuid
from datetime import datetime
from collections import defaultdict

import pydantic
import weakref

import muforge
from muforge.shared.utils import class_from_module

async def get_location(conn: Connection, node_name: str) -> "None | BaseLocation":
    if (found := muforge.LOCATIONS.get(node_name, None)):
        return found
    query = "SELECT * FROM locations WHERE node_name=$1 LIMIT 1"
    rows = await conn.fetch(query, node_name)
    if not rows:
        return None
    data = rows[0]
    path = data.pop("path")
    location_class = class_from_module(path)
    query = "SELECT component_name, data FROM location_components WHERE location_id=$1"
    rows = await conn.fetch(query, data['id'])
    components = {x['component_name']: x['data'] for x in rows}
    location = location_class.create(conn, data, components)
    muforge.LOCATIONS[node_name] = location
    return location


class BaseLocationComponent(pydantic.BaseModel):
    location: "BaseLocation" = pydantic.Field(exclude=True)

    @classmethod
    def create(cls, location: "BaseLocation", **data) -> "BaseLocationComponent":
        return cls(location=location, **data)

    @classmethod
    def path(cls) -> str:
        return f"{cls.__module__}.{cls.__name__}"


class BaseLocation(pydantic.BaseModel):
    id: uuid.UUID
    name: str
    node_name: str
    created_at: datetime
    description: str | None = None
    components: dict[str, BaseLocationComponent] = pydantic.Field(default_factory=dict, exclude=True)

    async def _get_entities_by_type(self, conn: Connection, entity_type: tuple[str, ...]) -> list[uuid.UUID]:
        query = "SELECT entity_id FROM entity_location_view WHERE entity_type IN ($1) AND location_id = $2 ORDER BY arrived_at"
        rows = await conn.fetch(query, entity_type, self.id)
        return [row['entity_id'] for row in rows]
    
    async def get_entities(self, conn: Connection) -> list[uuid.UUID]:
        query = "SELECT entity_id FROM entity_location_view WHERE location_id = $1 ORDER BY arrived_at"
        rows = await conn.fetch(query, self.id)
        return [row['entity_id'] for row in rows]
    
    async def get_entities_grouped(self, conn: Connection) -> dict[str, list[uuid.UUID]]:
        query = "SELECT entity_type, entity_id FROM entity_location_view WHERE location_id = $1 ORDER BY arrived_at"
        rows = await conn.fetch(query, self.id)
        grouped_entities = defaultdict(list)
        for row in rows:
            grouped_entities[row['entity_type']].append(row['entity_id'])
        return dict(grouped_entities)

    async def get_characters(self, conn: Connection) -> list[uuid.UUID]:
        return await self._get_entities_by_type(conn, ("character",))
    
    async def get_objects(self, conn: Connection) -> list[uuid.UUID]:
        return await self._get_entities_by_type(conn, ("object",))
    
    async def get_npcs(self, conn: Connection) -> list[uuid.UUID]:
        return await self._get_entities_by_type(conn, ("npc",))
    
    async def get_mobiles(self, conn: Connection) -> list[uuid.UUID]:
        return await self._get_entities_by_type(conn, ("character", "npc"))
    
    async def get_parent(self, conn: Connection) -> "None | BaseLocation":
        if "." not in self.node_name:
            return None
        par_path, this_node = self.node_name.rsplit(".", 1)
        return await get_location(conn, par_path)
    
    async def get_children(self, conn: Connection) -> "list[BaseLocation]":
        query = "SELECT id FROM locations WHERE parent = $1"
        rows = await conn.fetch(query, self.id)
        return [y for x in rows if (y := await get_location(conn, x['id']))]
    
    @classmethod
    def path(cls) -> str:
        return f"{cls.__module__}.{cls.__name__}"
    
    @classmethod
    def create(cls, conn: Connection, data, component_data) -> "BaseLocation":
        new_location = cls(**data)
        for comp_name, comp_data in component_data.items():
            if comp_class := muforge.LOCATION_COMPONENTS.get(comp_name, None):
                component = comp_class.create(location=new_location, **comp_data)
                new_location.components[comp_name] = component
        return new_location


# large overworld map type locations.
class Dimension(BaseLocation):
    pass


class Galaxy(BaseLocation):
    pass


class Sector(BaseLocation):
    pass


class StarSystem(BaseLocation):
    pass


class Planet(BaseLocation):
    pass


class Surface(BaseLocation):
    pass


class Settlement(BaseLocation):
    pass


# The below are action locations where entities can perform actions.
class _Action(BaseLocation):
    pass


class Field(_Action):
    pass


class Dungeon(_Action):
    pass