from __future__ import annotations
import game_schemas

import muforge

def validate_all():
    """Run once on startup to make sure all TOML/loaded objects conform to our fields."""
    # nodes
    if hasattr(muforge.REGISTRY, "nodes"):
        for node_id, node in muforge.REGISTRY.nodes.items():
            try:
                game_schemas.validate_node(node)
            except Exception as e:
                # don't crash the whole game, just report
                print(f"[schema] Node '{node_id}' failed validation: {e}")

    # rooms
    if hasattr(muforge.REGISTRY, "rooms"):
        for room_id, room in muforge.REGISTRY.rooms.items():
            try:
                game_schemas.validate_room(room)
            except Exception as e:
                print(f"[schema] Room '{room_id}' failed validation: {e}")

    # attributes (if present)
    attrs = getattr(muforge.REGISTRY, "attributes", {})
    for attr_id, attr in attrs.items():
        try:
            game_schemas.validate_attr(attr)
        except Exception as e:
            print(f"[schema] Attr '{attr_id}' failed validation: {e}")

    print("✅ Game schema validation completed (with warnings above if any).")
