import tomllib
from typing import Dict, List, Any
from pathlib import Path




def load_toml_file(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_node_schema(path: Path) -> NodeSchema:
    data = load_toml_file(path)
    return NodeSchema(**data)


def load_room_schema(path: Path) -> RoomSchema:
    data = load_toml_file(path)
    return RoomSchema(**data)


def load_attribute_schema(path: Path) -> AttributeSchema:
    data = load_toml_file(path)
    return AttributeSchema(**data)
