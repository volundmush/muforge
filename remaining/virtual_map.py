# virtual_map.py
from __future__ import annotations
import muforge


def build_grid(width: int = 50, height: int = 50, base_id: str = "grid") -> None:
    """
    Create a width x height grid of simple nodes and inject into the registry.
    Each node id looks like: grid.10.12
    Movement: north/south/east/west.
    """
    for y in range(height):
        for x in range(width):
            node_id = f"{base_id}.{x}.{y}"
            name = f"Grid Tile ({x},{y})"
            desc = "A procedurally generated tile."
            exits = {}
            # neighbors
            if x > 0:
                exits["West"] = f"{base_id}.{x-1}.{y}"
            if x < width - 1:
                exits["East"] = f"{base_id}.{x+1}.{y}"
            if y > 0:
                exits["North"] = f"{base_id}.{x}.{y-1}"
            if y < height - 1:
                exits["South"] = f"{base_id}.{x}.{y+1}"

            node_obj = type("VirtualNode", (), {})()
            node_obj.id = node_id
            node_obj.kind = "field"
            node_obj.name = name
            node_obj.desc = desc
            node_obj.exits = exits
            node_obj.controls = ["adventure"]  # you can adventure anywhere
            node_obj.meta = {}

            # register directly
            muforge.REGISTRY.nodes[node_id] = node_obj
