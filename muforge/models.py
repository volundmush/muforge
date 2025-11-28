# C:\Networking Project\muforge\muforge\models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

DEFAULT_START_NODE_ID = "node.planet.terra"


@dataclass
class Player:
    id: str
    name: str = "Demo Player"
    current_node_id: str = DEFAULT_START_NODE_ID
    # basic stats
    attributes: Dict[str, Any] = field(default_factory=lambda: {
        "health": 100,
        "max_health": 100,
        "credits": 0,
        "attack": 10,
        "armor": 0,
    })
    inventory: List[Dict[str, Any]] = field(default_factory=list)
    # NEW: store an active adventure field (dict)
    current_field: Optional[Dict[str, Any]] = None
    # NEW: track if loot was taken
    field_loot_taken: bool = False

    def to_dict(self) -> Dict[str, Any]:
        attrs = self.attributes
        return {
            "id": self.id,
            "name": self.name,
            "current_node_id": self.current_node_id,
            # expose key stats at top level for the frontend
            "health": attrs.get("health", 100),
            "max_health": attrs.get("max_health", 100),
            "credits": attrs.get("credits", 0),
            "attributes": attrs,
            "inventory": [
                {
                    "name": item.get("name"),
                    "qty": item.get("qty") or item.get("count") or item.get("amount") or 1,
                }
                for item in self.inventory
            ],
            "has_field": self.current_field is not None,
        }


class GameState:
    def __init__(self) -> None:
        self.players: Dict[str, Player] = {}

    def get_or_create_player(self, player_id: str) -> Player:
        if player_id not in self.players:
            self.players[player_id] = Player(id=player_id)
        return self.players[player_id]


game_state = GameState()
