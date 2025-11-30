# mutemplate/web_api.py

import os
import sys
import uuid
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)

# ---------- path setup ----------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
ENGINE_DIR = PROJECT_ROOT / "muforge"

for p in (PROJECT_ROOT, ENGINE_DIR):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# ---------- app ----------
app = FastAPI(title="Muforge Web API")
STATIC_DIR = CURRENT_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- try to import real engine ----------
loader_module = None
commands_module = None
models_module = None

try:
    loader_module = __import__("muforge.loader", fromlist=["*"])
    logging.info("✅ imported muforge.loader")
except ImportError:
    logging.warning("⚠ could not import muforge.loader")

try:
    commands_module = __import__("muforge.commands", fromlist=["*"])
    logging.info("✅ imported muforge.commands")
except ImportError:
    logging.warning("⚠ could not import muforge.commands")

try:
    models_module = __import__("muforge.models", fromlist=["*"])
    logging.info("✅ imported muforge.models")
except ImportError:
    logging.warning("⚠ could not import muforge.models")

# ---------- fallback world (used if your loader doesn't give nodes) ----------
WORLD: Dict[str, Dict[str, Any]] = {
    "node.planet.terra": {
        "id": "node.planet.terra",
        "name": "Terra",
        "desc": "A well-mapped starter world. Entry point for all adventurers.",
        "lore": "Terra is the hub of expansion; guilds recruit here.",
        "grid": {"region": "Core", "x": 0, "y": 0},
        "exits": {
            "nova_city": "node.city.nova",
            "raider_outskirts": "node.field.raiders"
        },
        "kind": "planet",
    },
    "node.city.nova": {
        "id": "node.city.nova",
        "name": "Nova City",
        "desc": "Bustling neon market, lots of rumors and contracts.",
        "lore": "Nova grew around the first jump gate.",
        "grid": {"region": "Core", "x": 1, "y": 0},
        "exits": {
            "back_to_terra": "node.planet.terra",
            "lower_district": "node.city.lower"
        },
        "kind": "city",
    },
    "node.field.raiders": {
        "id": "node.field.raiders",
        "name": "Raider Outskirts",
        "desc": "Sparse dunes. Raider signals detected.",
        "lore": "Patrolled by mercs... and raiders.",
        "grid": {"region": "Outer", "x": -1, "y": 1},
        "exits": {
            "back_to_terra": "node.planet.terra"
        },
        "kind": "field",
    },
    "node.city.lower": {
        "id": "node.city.lower",
        "name": "Nova: Lower District",
        "desc": "Shady alleys where info is cheap.",
        "lore": "Fixers operate here.",
        "grid": {"region": "Core", "x": 1, "y": -1},
        "exits": {
            "nova_plaza": "node.city.nova"
        },
        "kind": "district",
    },
}

# ---------- detect loader functions ----------
if loader_module:
    loader_fn = (
        getattr(loader_module, "load_all_nodes", None)
        or getattr(loader_module, "load_nodes", None)
        or getattr(loader_module, "load_world", None)
        or getattr(loader_module, "load", None)
    )
else:
    loader_fn = None

if loader_fn is None:
    def loader_fn():
        logging.info("using built-in WORLD")
else:
    logging.info("using muforge loader")

# try to get node accessor from muforge
if loader_module:
    get_node_real = (
        getattr(loader_module, "get_node", None)
        or getattr(loader_module, "get", None)
        or getattr(loader_module, "get_room", None)
    )
else:
    get_node_real = None

def get_node(node_id: str):
    if get_node_real:
        return get_node_real(node_id)
    # fallback to our WORLD
    return WORLD.get(node_id)

# command execution
if commands_module and hasattr(commands_module, "execute_command"):
    execute_command_real = commands_module.execute_command
else:
    execute_command_real = None

def execute_command_simple(command: str, args, player: dict, session: dict) -> dict:
    """
    Handle simple commands from /api/game/command.

    We use this for inventory item usage (use <item name>),
    working directly on the player dict stored in the session.
    """

    text = (command or "").strip()
    if not text:
        return {"ok": False, "msg": "Empty command."}

    parts = text.split()
    cmd = parts[0].lower()
    extra = parts[1:]

    # args may come from JSON body; merge both sources
    arg_list = list(extra) + list(args or [])

    # For now, only support 'use'
    if cmd != "use":
        return {
            "ok": False,
            "msg": f"Command '{cmd}' is not supported via this endpoint."
        }

    if not arg_list:
        return {"ok": False, "msg": "Use what?"}

    item_name = " ".join(arg_list).strip()
    if not item_name:
        return {"ok": False, "msg": "Use what?"}

    # --- find item in inventory -------------------------------------------
    inventory = player.get("inventory") or []
    idx = None
    item = None

    for i, it in enumerate(inventory):
        name = (it.get("name") or it.get("item") or "").strip()
        if name.lower() == item_name.lower():
            idx = i
            item = it
            break

    if item is None:
        return {"ok": False, "msg": f"You don't have a {item_name}."}

    qty = item.get("qty") or item.get("count") or item.get("amount") or 1

    # --- load stats -------------------------------------------------------
    attrs = player.get("attributes") or {}

    health = attrs.get("health", player.get("health", 100))
    max_health = attrs.get("max_health", player.get("max_health", 100))
    credits = attrs.get("credits", player.get("credits", 0))
    attack = attrs.get("attack", player.get("attack", 10))
    armor = attrs.get("armor", player.get("armor", 0))

    name = item.get("name") or item_name

    heal = 0
    credits_gain = 0
    attack_gain = 0
    max_hp_gain = 0

    # --- item effects -----------------------------------------------------
    if name == "Medpack":
        heal = 25 * qty
    elif name == "Nano Repair Kit":
        heal = 75 * qty
    elif name == "Energy Cell":
        heal = 10 * qty
    elif name == "Charge Cell":
        heal = 5 * qty

    elif name == "Credits":
        credits_gain = 1 * qty
    elif name == "Iron Scrap":
        credits_gain = 2 * qty
    elif name == "Scrap":
        credits_gain = 3 * qty
    elif name == "Scrap Alloy":
        credits_gain = 5 * qty

    elif name in ("Weapon", "Plasma Blaster", "Blaster"):
        # basic weapon vs blaster
        attack_gain = 10 * qty if name in ("Blaster", "Plasma Blaster") else 5 * qty

    elif name in ("Armor", "Energy Shield"):
        max_hp_gain = 20 * qty

    else:
        return {"ok": False, "msg": f"{name} cannot be used directly."}

    msg_parts = [f"You use {qty}× {name}."]

    # healing, capped by max HP (including any boost)
    if heal > 0:
        new_hp = min(max_health + max_hp_gain, health + heal)
        actual_heal = new_hp - health
        health = new_hp
        if actual_heal > 0:
            msg_parts.append(f"Recovered {actual_heal} HP.")

    # max HP boost (e.g. Armor, Energy Shield) → also full heal
    if max_hp_gain > 0:
        max_health += max_hp_gain
        health = max_health
        msg_parts.append(f"Max health increased by {max_hp_gain}.")

    if credits_gain > 0:
        credits += credits_gain
        msg_parts.append(f"Gained {credits_gain} credits.")

    if attack_gain > 0:
        attack += attack_gain
        msg_parts.append(f"Attack increased by {attack_gain}.")

    # --- write stats back into player/attributes --------------------------
    attrs["health"] = health
    attrs["max_health"] = max_health
    attrs["credits"] = credits
    attrs["attack"] = attack
    attrs["armor"] = armor

    player["attributes"] = attrs
    player["health"] = health
    player["max_health"] = max_health
    player["credits"] = credits

    # consume the stack
    inventory.pop(idx)
    player["inventory"] = inventory

    # persist into session
    session["player"] = player

    return {
        "ok": True,
        "msg": " ".join(msg_parts),
        "player": player,
    }

# ---------- sessions ----------
sessions: Dict[str, Dict[str, Any]] = {}

# ---------- models ----------


@app.on_event("startup")
async def startup():
    loader_fn()
    logging.info("✅ game data ready")

# ---------- helpers ----------
def create_player() -> Dict[str, Any]:
    return {
        "id": "player_1",
        "name": "Traveler",
        "health": 100,
        "max_health": 100,
        "credits": 0,
        "level": 1,
        "xp": 0,
        "xp_to_next": 50,
        "current_node_id": "node.planet.terra",
        "inventory": [],
    }

def generate_raider_group(player: Dict[str, Any]) -> Dict[str, Any]:
    # enemy count capped by level
    max_enemies = min(4, player["level"] + 1)
    import random
    count = random.randint(1, max_enemies)
    enemies = []
    for i in range(count):
        raider_level = max(1, player["level"] + (1 if random.random() > 0.7 else 0))
        base_hp = 30 + raider_level * 10
        enemies.append({
            "id": i,
            "name": f"Raider L{raider_level}",
            "level": raider_level,
            "health": base_hp,
            "max_health": base_hp,
            "attack_min": 4 + raider_level,
            "attack_max": 9 + raider_level * 2,
            "xp_reward": 15 + raider_level * 5,
            "credit_reward": 3 + raider_level,
        })
    return {
        "enemies": enemies,
        "story": "A patrol of raiders spots you in the dunes.",
        "loot": [
            {"name": "Scrap Alloy", "qty": 1},
            {"name": "Charge Cell", "qty": 1},
        ]
    }

def grant_xp_and_level(player: Dict[str, Any], amount: int) -> List[str]:
    msgs = []
    player["xp"] += amount
    msgs.append(f"You gained {amount} XP.")
    # level up loop
    while player["xp"] >= player["xp_to_next"]:
        player["xp"] -= player["xp_to_next"]
        player["level"] += 1
        player["max_health"] += 10
        player["health"] = player["max_health"]
        player["xp_to_next"] = int(player["xp_to_next"] * 1.35)
        msgs.append(f"Level up! You are now level {player['level']}.")
    return msgs

# ---------- routes ----------

