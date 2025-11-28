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
    })
    inventory: List[Dict[str, Any]] = field(default_factory=list)
    # NEW: store an active adventure field (dict)
    current_field: Optional[Dict[str, Any]] = None
    # NEW: track if loot was taken
    field_loot_taken: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "current_node_id": self.current_node_id,
            "attributes": self.attributes,
            "inventory": self.inventory,
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
