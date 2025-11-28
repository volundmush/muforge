from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any
from pathlib import Path
import sys

try:
    import tomllib  # py 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import toml as tomllib  # type: ignore


@dataclass
class NodeSchema:
    id: str
    kind: str
    name: str
    desc: str
    exits: Dict[str, str] = field(default_factory=dict)
    controls: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoomSchema:
    id: str
    kind: str
    name: str
    desc: str
    controls: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttributeSchema:
    id: str
    name: str
    desc: str
    base: int
    max: int


def load_toml_file(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        if "tomllib" in sys.modules:
            return tomllib.load(f)
        else:  # pragma: no cover
            text = f.read().decode("utf-8")
            return tomllib.loads(text)


def load_node_schema(path: Path) -> NodeSchema:
    data = load_toml_file(path)
    return NodeSchema(
        id=data["id"],
        kind=data.get("kind", "node"),
        name=data["name"],
        desc=data.get("desc", ""),
        exits=data.get("exits", {}),
        controls=data.get("controls", []),
        meta=data.get("meta", {}),
    )


def load_room_schema(path: Path) -> RoomSchema:
    data = load_toml_file(path)
    return RoomSchema(
        id=data["id"],
        kind=data.get("kind", "room"),
        name=data["name"],
        desc=data.get("desc", ""),
        controls=data.get("controls", []),
        meta=data.get("meta", {}),
    )


def load_attribute_schema(path: Path) -> AttributeSchema:
    data = load_toml_file(path)
    return AttributeSchema(
        id=data["id"],
        name=data["name"],
        desc=data.get("desc", ""),
        base=int(data.get("base", 0)),
        max=int(data.get("max", 0)),
    )
