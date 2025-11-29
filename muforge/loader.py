from __future__ import annotations
from pathlib import Path
from typing import Dict

from .schemas import (
    load_node_schema,
    load_room_schema,
    load_attribute_schema,
    NodeSchema,
    RoomSchema,
    AttributeSchema,
)

class Registry:
    def __init__(self) -> None:
        self.nodes: Dict[str, NodeSchema] = {}
        self.rooms: Dict[str, RoomSchema] = {}
        self.attributes: Dict[str, AttributeSchema] = {}

    def load_all(self) -> None:
        data = Path.cwd() / "data"

        NODE_DIR = data / "nodes"
        ROOM_DIR = data / "rooms"
        ATTR_DIR = data / "attributes"

        if NODE_DIR.exists():
            for path in NODE_DIR.glob("*.toml"):
                node = load_node_schema(path)
                self.nodes[node.id] = node

        if ROOM_DIR.exists():
            for path in ROOM_DIR.glob("*.toml"):
                room = load_room_schema(path)
                self.rooms[room.id] = room

        if ATTR_DIR.exists():
            for path in ATTR_DIR.glob("*.toml"):
                attr = load_attribute_schema(path)
                self.attributes[attr.id] = attr

    def get_node(self, node_id: str) -> NodeSchema | None:
        return self.nodes.get(node_id)

    def get_room(self, room_id: str) -> RoomSchema | None:
        return self.rooms.get(room_id)

    def get_attribute(self, attr_id: str) -> AttributeSchema | None:
        return self.attributes.get(attr_id)

registry = Registry()