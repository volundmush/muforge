from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import random


@dataclass
class Enemy:
    id: int           # <- so we can do: attack 1
    name: str
    health: int
    attack: int


@dataclass
class AdventureField:
    id: str
    name: str
    desc: str
    enemies: List[Enemy]
    rewards: List[Dict[str, Any]]


def generate_adventure_field(source_node_id: str) -> AdventureField:
    """Create a small combat zone with 1–3 enemies and some rewards."""
    enemy_count = random.randint(1, 3)
    enemies: List[Enemy] = []
    for i in range(enemy_count):
        enemies.append(
            Enemy(
                id=i + 1,  # important: 1-based ids for user commands
                name=f"Raider {i+1}",
                health=random.randint(15, 30),
                attack=random.randint(2, 6),
            )
        )

    rewards = [
        {"name": "Credits", "amount": random.randint(5, 20)},
        {"name": "Scrap", "amount": random.randint(1, 3)},
    ]

    return AdventureField(
        id=f"adventure.{source_node_id}",
        name="Generated Field",
        desc="A quickly generated combat zone.",
        enemies=enemies,
        rewards=rewards,
    )


def field_to_dict(field: AdventureField) -> Dict[str, Any]:
    """Turn the AdventureField into plain dicts so we can store it on the player."""
    return {
        "id": field.id,
        "name": field.name,
        "desc": field.desc,
        "enemies": [asdict(e) for e in field.enemies],
        "rewards": field.rewards,
    }
