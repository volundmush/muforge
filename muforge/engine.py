from __future__ import annotations
from typing import Dict, Any

from .models import game_state
from .commands import exec_command, CommandError
import muforge


def get_player_state(player_id: str) -> Dict[str, Any]:
    player = game_state.get_or_create_player(player_id)
    node = muforge.NODES.get(player.current_node_id)
    return {
        "player": player.to_dict(),
        "node": {
            "id": node.id if node else None,
            "name": node.name if node else None,
            "desc": node.desc if node else None,
            "exits": node.exits if node else {},
            "controls": node.controls if node else [],
        },
    }


def run_player_command(player_id: str, command: str) -> Dict[str, Any]:
    player = game_state.get_or_create_player(player_id)
    try:
        result = exec_command(player, command)
        return {"ok": True, "result": result}
    except CommandError as e:
        return {"ok": False, "error": str(e)}
