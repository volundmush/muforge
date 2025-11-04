from __future__ import annotations
from typing import Dict, Any, Tuple, Optional, List
from collections import deque

from .loader import registry
from .models import Player
from .procedural import generate_adventure_field, field_to_dict


class CommandError(Exception):
    pass


def parse_command(raw: str) -> Tuple[str, str]:
    parts = raw.strip().split(maxsplit=1)
    if not parts:
        raise CommandError("Empty command.")
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    return cmd, arg


def _ensure_field(player: Player) -> Dict[str, Any]:
    if not player.current_field:
        raise CommandError("You are not in an adventure right now.")
    return player.current_field


def _bfs_path(start_id: str, target_id: str) -> Optional[List[str]]:
    """Simple breadth-first search over node exits to build a path."""
    q = deque([start_id])
    came_from = {start_id: None}
    while q:
        current = q.popleft()
        if current == target_id:
            # reconstruct
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        node = registry.get_node(current)
        if not node:
            continue
        for label, nxt in node.exits.items():
            # skip 'controls' accidentally in exits
            if label == "controls":
                continue
            if nxt not in came_from:
                came_from[nxt] = current
                q.append(nxt)
    return None


def exec_command(player: Player, raw: str) -> Dict[str, Any]:
    cmd, arg = parse_command(raw)

    node = registry.get_node(player.current_node_id)
    if not node:
        raise CommandError(f"Current node {player.current_node_id} not found.")

    # -------- basic inspection ----------
    if cmd == "look":
        return {
            "ok": True,
            "msg": f"{node.name}: {node.desc}",
            "node": {
                "id": node.id,
                "name": node.name,
                "desc": node.desc,
                "exits": node.exits,
                "controls": node.controls,
            },
        }

    if cmd == "whereami":
        return {
            "ok": True,
            "msg": f"You are at {node.name} ({node.id}).",
            "node": {
                "id": node.id,
                "name": node.name,
                "desc": node.desc,
                "exits": node.exits,
                "controls": node.controls,
            },
        }

    if cmd == "info":
        if not arg:
            raise CommandError("info needs an id, e.g. 'info node.city.nova'")
        # try node
        target = registry.get_node(arg)
        if target:
            return {
                "ok": True,
                "msg": f"{target.name}: {target.desc}",
                "node": {
                    "id": target.id,
                    "name": target.name,
                    "desc": target.desc,
                    "exits": target.exits,
                    "controls": target.controls,
                },
            }
        # try room
        room = registry.get_room(arg)
        if room:
            return {
                "ok": True,
                "msg": f"{room.name}: {room.desc}",
            }
        raise CommandError(f"No node or room with id '{arg}'.")

    if cmd == "pathfind":
        if not arg:
            raise CommandError("pathfind needs a target node id, e.g. 'pathfind node.city.nova'")
        path = _bfs_path(player.current_node_id, arg)
        if not path:
            raise CommandError(f"No path from {player.current_node_id} to {arg}.")
        return {
            "ok": True,
            "msg": f"Path: {' -> '.join(path)}",
            "path": path,
        }

    # -------- movement ----------
    if cmd == "visit":
        if not arg:
            raise CommandError("visit requires an exit name.")
        if arg not in node.exits:
            raise CommandError(f"No exit named '{arg}' here.")
        target_id = node.exits[arg]
        target = registry.get_node(target_id)
        if not target:
            raise CommandError(f"Target node {target_id} not found.")
        player.current_node_id = target_id
        # moving clears adventure
        player.current_field = None
        player.field_loot_taken = False
        return {
            "ok": True,
            "msg": f"You move to {target.name}.",
            "node": {
                "id": target.id,
                "name": target.name,
                "desc": target.desc,
                "exits": target.exits,
                "controls": target.controls,
            },
        }

    # -------- adventure ----------
    if cmd == "adventure":
        if "adventure" not in node.controls:
            raise CommandError("You cannot adventure here.")
        field = generate_adventure_field(node.id)
        as_dict = field_to_dict(field)
        player.current_field = as_dict
        player.field_loot_taken = False
        return {
            "ok": True,
            "msg": "Adventure field created.",
            "field": as_dict,
        }

    if cmd == "attack":
        if not arg:
            raise CommandError("attack requires an enemy number.")
        field = _ensure_field(player)
        try:
            enemy_num = int(arg)
        except ValueError:
            raise CommandError("enemy number must be an integer.")
        enemies = field.get("enemies", [])
        enemy = None
        for e in enemies:
            if e["id"] == enemy_num:
                enemy = e
                break
        if not enemy:
            raise CommandError(f"No enemy {enemy_num} here.")
        enemy["health"] -= 10
        msg = f"You hit {enemy['name']} for 10 damage. ({max(enemy['health'], 0)} HP left)"
        field["enemies"] = [e for e in enemies if e["health"] > 0]
        if not field["enemies"]:
            msg += " All enemies defeated! You can 'loot' now."
        return {
            "ok": True,
            "msg": msg,
            "field": field,
        }

    if cmd == "loot":
        field = _ensure_field(player)
        if player.field_loot_taken:
            raise CommandError("You already took the loot.")
        rewards = field.get("rewards", [])
        for r in rewards:
            player.inventory.append(r)
        player.field_loot_taken = True
        return {
            "ok": True,
            "msg": "You collect the spoils.",
            "rewards": rewards,
            "inventory": player.inventory,
        }

    if cmd == "heal":
        max_hp = player.attributes.get("max_health", 100)
        player.attributes["health"] = max_hp
        return {
            "ok": True,
            "msg": f"You feel restored. Health is now {max_hp}.",
        }

    # -------- search/pickup ----------
    if cmd == "search":
        import random
        possible = [
            {"name": "Medpack", "amount": 1},
            {"name": "Energy Cell", "amount": 2},
            {"name": "Iron Scrap", "amount": 3},
            {"name": "Nano Repair Kit", "amount": 1},
            {"name": "Credits", "amount": 10},
        ]
        found = []
        if random.random() < 0.7:
            found = random.sample(possible, k=random.randint(1, 2))
            player.found_items = found
            return {"ok": True, "msg": f"You search {node.name} and discover some items.", "found": found}
        else:
            player.found_items = []
            return {"ok": True, "msg": "You search carefully but find nothing."}

    if cmd == "pickup":
        if not getattr(player, "found_items", None):
            return {"ok": False, "msg": "There’s nothing here to pick up."}
        player.inventory.extend(player.found_items)
        names = ", ".join([i["name"] for i in player.found_items])
        player.found_items = []
        return {"ok": True, "msg": f"You pick up {names}."}

    if cmd == "inventory":
        return {"ok": True, "msg": "You are carrying:", "items": player.inventory}

    if cmd == "interact":
        shops = node.meta.get("shop_ids", [])
        if not shops:
            return {"ok": True, "msg": "Nothing to interact with here."}
        shop_objs = []
        for sid in shops:
            shop = registry.get_room(sid)
            if shop:
                shop_objs.append(
                    {
                        "id": shop.id,
                        "name": shop.name,
                        "desc": shop.desc,
                        "inventory": shop.meta.get("inventory", []),
                    }
                )
        return {
            "ok": True,
            "msg": "Interactables found.",
            "shops": shop_objs,
        }

    if cmd == "help":
        return {
            "ok": True,
            "msg": "Commands: look, whereami, info <id>, pathfind <id>, visit <exit>, adventure, attack <n>, loot, heal, search, pickup, inventory, interact, help",
        }

    raise CommandError(f"Unknown command '{cmd}'.")
