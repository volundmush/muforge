from __future__ import annotations
from typing import Dict, Any, List


class SchemaError(Exception):
    pass


NODE_REQUIRED = ["id", "kind", "name", "desc"]
NODE_OPTIONAL = ["exits", "controls", "meta"]

ROOM_REQUIRED = ["id", "kind", "name", "desc"]
ROOM_OPTIONAL = ["controls", "meta"]

ATTR_REQUIRED = ["id", "name"]
ATTR_OPTIONAL = ["desc", "base", "max"]


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Accept either a dict or an object with attributes and return a dict."""
    if isinstance(obj, dict):
        return obj
    # try attrs
    data = {}
    for attr in dir(obj):
        if attr.startswith("_"):
            continue
        val = getattr(obj, attr)
        # skip callables
        if callable(val):
            continue
        data[attr] = val
    return data


def _check_required(data: Dict[str, Any], required: List[str], label: str):
    missing = [f for f in required if f not in data]
    if missing:
        raise SchemaError(f"{label} missing required fields: {', '.join(missing)}")


def validate_node(node_obj: Any) -> Dict[str, Any]:
    data = _to_dict(node_obj)
    _check_required(data, NODE_REQUIRED, "Node")
    data.setdefault("exits", {})
    data.setdefault("controls", [])
    data.setdefault("meta", {})
    return data


def validate_room(room_obj: Any) -> Dict[str, Any]:
    data = _to_dict(room_obj)
    _check_required(data, ROOM_REQUIRED, "Room")
    data.setdefault("controls", [])
    data.setdefault("meta", {})
    return data


def validate_attr(attr_obj: Any) -> Dict[str, Any]:
    data = _to_dict(attr_obj)
    _check_required(data, ATTR_REQUIRED, "Attr")
    return data
