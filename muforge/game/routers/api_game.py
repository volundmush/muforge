from typing import Annotated, Optional, List

from pydantic import BaseModel

import muforge
import jwt
import uuid
import random

from fastapi import APIRouter, Depends, Body, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordRequestForm

from muforge.shared.models.auth import TokenResponse, UserLogin, RefreshTokenModel

from ..db import users as users_db, auth as auth_db
from muforge.shared.utils import crypt_context
from .utils import get_real_ip

class CommandRequest(BaseModel):
    session_id: uuid.UUID
    command: str
    args: Optional[List[str]] = []

class ShopBuyRequest(BaseModel):
    session_id: uuid.UUID
    item_name: str

class SearchRequest(BaseModel):
    session_id: uuid.UUID

router = APIRouter()

def get_session(session_id: uuid.UUID):
    if (session := muforge.SESSIONS.get(session_id, None)) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/api/ping")
async def ping():
    return {"status": "ok"}

@router.post("/start")
async def start_game():
    session_id = str(uuid.uuid4())

    player = {
        "name": "Traveler",
        "health": 100,
        "max_health": 100,
        "xp": 0,
        "xp_to_next": 50,
        "level": 1,
        "credits": 0,
        "inventory": [],
    }

    node = {
        "id": "terra",
        "name": "Terra",
        "desc": "The home planet. Your journey begins here.",
    }

    sessions[session_id] = {
        "player": player,
        "node": node,
        "combat": None,
        "unclaimed_loot": [],
    }

    return {"session_id": session_id}

@router.get("/state")
async def get_game_state(session_id: uuid.UUID = Query(...)):
    session = get_session(session_id)

    return {
        "player": session["player"],
        "node": session["node"],
        "combat": session["combat"],
        "loot": session.get("unclaimed_loot", []),
    }

@router.post("/command")
async def run_command(req: CommandRequest):
    session = get_session(req.session_id)

    player = session["player"]

    if execute_command_real:
        result = execute_command_real(
            command=req.command,
            args=req.args or [],
            player=player,
            session=session,
        )
        # Legacy format conversion
        return {
            "success": result.get("success", True),
            "message": result.get("message", ""),
            "data": result.get("data", {}),
        }
    else:
        result = execute_command_simple(req.command, req.args or [], player, session)
        # New format: {ok, msg, player}
        return {
            "ok": result.get("ok", False),
            "msg": result.get("msg", ""),
            "error": result.get("msg", "") if not result.get("ok") else None,
            "player": result.get("player", player),
        }
    
@router.post("/heal")
async def heal_player(session_id: uuid.UUID = Query(...)):
    session = get_session(session_id)

    player = session.active_character()

    amount = 15
    player.health = min(player.max_health, player.health + amount)

    return {
        "message": f"Healed for {amount}",
        "player": player.to_dict()
    }

@router.post("/shop/buy")
async def shop_buy(req: ShopBuyRequest):
    session = get_session(req.session_id)

    player = session["player"]

    # Basic prices – keep in sync with your front-end ITEM_DATABASE
    PRICES = {
        "Medpack": 25,
        "Nano Repair Kit": 50,
        "Energy Cell": 10,
        "Charge Cell": 5,
        "Armor": 80,
        "Energy Shield": 100,
        "Weapon": 60,
        "Blaster": 90,
        "Plasma Blaster": 90,
    }

    name = req.item_name
    cost = PRICES.get(name)
    if cost is None:
        return {"ok": False, "msg": f"{name} cannot be bought here."}

    credits = player.get("credits", 0)
    if credits < cost:
        return {"ok": False, "msg": "Not enough credits."}

    credits -= cost
    player["credits"] = credits

    inv = player.get("inventory") or []
    # normalize to the same shape we use in /state
    inv.append({"name": name, "qty": 1})
    player["inventory"] = inv

    session["player"] = player

    return {
        "ok": True,
        "msg": f"Purchased {name} for {cost} credits!",
        "player": player,
    }

MAX_INVENTORY_SLOTS = 6   # keep in sync with frontend

@router.post("/search")
async def search(req: SearchRequest):
    session = get_session(req.session_id)

    player = session["player"]

    inventory = player.get("inventory") or []

    # inventory full → nothing added
    if len(inventory) >= MAX_INVENTORY_SLOTS:
        return {
            "ok": False,
            "msg": "Your inventory is full. You leave any scraps you find behind.",
            "player": player,
            "items": [],
            "credits_gained": 0,
        }

    # simple loot table – adjust however you like
    loot_table = [
        ("Scrap Alloy", 1),
        ("Scrap", 1),
        ("Iron Scrap", 1),
        ("Energy Cell", 1),
        ("Nano Repair Kit", 1),
        ("Medpack", 1),
    ]

    # 1–2 rolls of random junk
    rolls = random.randint(1, 2)
    found_items = []
    for _ in range(rolls):
        if len(inventory) >= MAX_INVENTORY_SLOTS:
            break
        name, qty = random.choice(loot_table)
        inventory.append({"name": name, "qty": qty})
        found_items.append({"name": name, "qty": qty})

    # small credit bonus
    credits_gain = random.randint(5, 25)
    credits = player.get("credits", 0) + credits_gain
    player["credits"] = credits

    player["inventory"] = inventory
    session["player"] = player

    return {
        "ok": True,
        "msg": "You scour the area and find some useful scraps.",
        "player": player,
        "items": found_items,
        "credits_gained": credits_gain,
    }

@router.post("/adventure")
async def start_adventure(session_id: uuid.UUID = Query(...)):
    session = get_session(session_id)

    player = session["player"]

    # simple 1–2 raiders
    enemy_count = random.randint(1, 2)
    enemies = []
    for i in range(enemy_count):
        level = random.randint(player["level"], player["level"] + 1)
        max_hp = 40 + level * 10
        enemies.append({
            "id": i,
            "name": f"Raider L{level}",
            "health": max_hp,
            "max_health": max_hp,
            "attack": 8 + level * 2,
            "level": level,
            "credit_reward": 10 + level * 5,  # Base reward scales with level
        })

    combat = {"enemies": enemies}
    session["combat"] = combat

    # Pre-generate loot for this fight
    loot = [
        {"name": "Credits", "count": random.randint(20, 60)},
        {"name": "Scrap Alloy", "count": random.randint(1, 4)},
    ]
    session["unclaimed_loot"] = loot

    return {
        "enemies": enemies,
        "description": "You encounter hostile raiders in the outskirts.",
        "loot": loot,
    }

@router.post("/attack")
async def attack_enemy(
    session_id: uuid.UUID = Query(...),
    enemy_id: int = Query(...),
):
    session = get_session(session_id)

    player = session["player"]
    combat = session.get("combat")
    if not combat:
        raise HTTPException(status_code=400, detail="No active combat")

    enemies = combat["enemies"]

    # enemy_id is the enemy's stable "id" field, not its index
    target_index = None
    for i, enemy in enumerate(enemies):
        if enemy.get("id") == enemy_id:
            target_index = i
            break

    if target_index is None:
        raise HTTPException(status_code=400, detail="Invalid enemy id")

    import random
    events: list[str] = []

    # Player attack
    enemy = enemies[target_index]
    dmg = random.randint(12, 20)
    enemy["health"] = max(0, enemy["health"] - dmg)
    events.append(f"You hit {enemy['name']} for {dmg} damage.")

    # Remove dead enemy and grant rewards
    if enemy["health"] <= 0:
        events.append(f"{enemy['name']} is defeated!")
        # Grant credit reward
        credit_reward = enemy.get("credit_reward", 0)
        if credit_reward > 0:
            player["credits"] += credit_reward
            events.append(f"You loot {credit_reward} credits from {enemy['name']}.")
        enemies.pop(target_index)

    combat_won = False
    loot_to_send = []

    # Enemy turn (only if any left)
    if enemies:
        enemy = random.choice(enemies)
        edmg = random.randint(5, enemy["attack"])
        player["health"] = max(0, player["health"] - edmg)
        events.append(f"{enemy['name']} hits you for {edmg} damage.")
        
        # Check for player death
        if player["health"] <= 0:
            return {
                "events": events + ["You were defeated!"],
                "combat_won": False,
                "player_dead": True,
                "enemies": enemies,
                "player": player,
            }
    else:
        combat_won = True
        session["combat"] = None
        loot_to_send = session.get("unclaimed_loot", [])

    return {
        "events": events,
        "combat_won": combat_won,
        "enemies": enemies,
        "loot": loot_to_send,
        "player": player,
    }

@router.post("/loot/claim")
async def claim_loot(session_id: uuid.UUID = Query(...)):
    session = get_session(session_id)

    player = session["player"]
    loot = session.get("unclaimed_loot", [])

    if "inventory" not in player or player["inventory"] is None:
        player["inventory"] = []

    # Move loot into inventory
    for item in loot:
        if item["name"] == "Credits":
            player["credits"] += item.get("count", 0)
        else:
            player["inventory"].append({
                "name": item["name"],
                "count": item.get("count", 1),
            })

    session["unclaimed_loot"] = []

    return {
        "claimed": loot,
        "player": player,
    }

@router.post("/unlock")
async def unlock_location(session_id: uuid.UUID = Query(...), location_id: str = Query(...)):
    session = get_session(session_id)
    
    player = session["player"]

    # Example costs (Delta Base = 50 credits)
    unlock_costs = {
        "delta_base": 50,
        "node.delta.base": 50
    }

    if location_id not in unlock_costs:
        return {"success": False, "message": "Unknown locked location."}

    cost = unlock_costs[location_id]

    if player["credits"] < cost:
        return {"success": False, "message": "Not enough credits."}

    # Subtract credits
    player["credits"] -= cost

    # Mark as unlocked
    if "unlocked_locations" not in player:
        player["unlocked_locations"] = []

    player["unlocked_locations"].append(location_id)

    return {
        "success": True,
        "message": f"Unlocked {location_id}!",
        "player": player
    }



