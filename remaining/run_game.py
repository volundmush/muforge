import asyncio

import muforge
from dynaconf import Dynaconf

from muforge.engine import get_player_state, run_player_command
from muforge.game.application import Application as GameApplication
from muforge.shared.utils import run_program
from game_loader import validate_all
from virtual_map import build_grid
# try color
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except Exception:
    class _F:  # fallback
        RED = GREEN = YELLOW = CYAN = WHITE = ""
    class _S:
        BRIGHT = RESET_ALL = ""
    Fore, Style = _F(), _S()


settings = Dynaconf(environments=True, settings_files=[], envvar_prefix=False)
settings.set("GAME", {})
settings.set("MSSP", {"NAME": "Demo MUD"})


async def patched_setup(self: GameApplication):
    await super(GameApplication, self).setup()
GameApplication.setup = patched_setup

validate_all()
build_grid(50, 50, "grid")

def print_node(node: dict):
    print()
    print(f"{Style.BRIGHT}{Fore.CYAN}== {node['name']} =={Style.RESET_ALL}")
    print(node["desc"])
    if node.get("exits"):
        print(f"\n{Fore.YELLOW}Exits:{Style.RESET_ALL}")
        for label in node["exits"].keys():
            print(f"  • {label}")
    if node.get("controls"):
        print(f"{Fore.MAGENTA}Actions:{Style.RESET_ALL} " + ", ".join(node["controls"]))
    print()


def print_field(field: dict):
    print()
    print(f"{Style.BRIGHT}{Fore.RED}⚔ Generated Field ⚔{Style.RESET_ALL}")
    print(field["desc"])
    enemies = field.get("enemies", [])
    if enemies:
        print(f"\n{Fore.YELLOW}Enemies:{Style.RESET_ALL}")
        for e in enemies:
            print(f"  • [{e['id']}] {e['name']} (HP {e['health']}, ATK {e['attack']})")
    else:
        print(f"\n{Fore.GREEN}All enemies defeated. You can 'loot' now.{Style.RESET_ALL}")
    rewards = field.get("rewards", [])
    if rewards:
        print(f"\n{Fore.GREEN}Rewards:{Style.RESET_ALL}")
        for r in rewards:
            print(f"  • {r['name']} ×{r['amount']}")
    print()


def print_inventory(items: list):
    if not items:
        print(f"{Fore.YELLOW}Your inventory is empty.{Style.RESET_ALL}")
        return
    print(f"{Style.BRIGHT}{Fore.GREEN}Inventory:{Style.RESET_ALL}")
    for it in items:
        name = it.get("name", "Unknown")
        amt = it.get("amount")
        if amt is not None:
            print(f"  • {name} x{amt}")
        else:
            print(f"  • {name}")
    print()


async def patched_run(self: GameApplication):
    print(f"{Style.BRIGHT}{Fore.GREEN}MUD demo is running. Type commands, 'quit' to exit.{Style.RESET_ALL}")

    player_id = "demo"
    state = get_player_state(player_id)
    node = state["node"]
    print_node(node)

    while True:
        try:
            cmd = input(f"{Fore.WHITE}> {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye, adventurer!")
            break

        if cmd.lower() in ("quit", "exit"):
            print("Goodbye, adventurer!")
            break

        resp = run_player_command(player_id, cmd)
        if not resp["ok"]:
            print(f"{Fore.RED}! {resp['error']}{Style.RESET_ALL}")
            continue

        res = resp["result"]

        # 1) always show main message if it exists
        msg = res.get("msg")
        if msg:
            print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

        # 2) show node view if we moved or looked
        node_data = res.get("node")
        if node_data:
            print_node(node_data)

        # 3) show field view if we adventured or attacked
        field_data = res.get("field")
        if field_data:
            print_field(field_data)

        # 4) show items we just found via search
        if "found" in res:
            print(f"{Fore.CYAN}You found:{Style.RESET_ALL}")
            for item in res["found"]:
                print(f"  • {item['name']} ×{item['amount']}")

        # 5) show inventory results
        if "items" in res:
            print_inventory(res["items"])

        # 6) show loot we just took
        if "rewards" in res and res["rewards"]:
            print(f"{Fore.GREEN}Loot gained:{Style.RESET_ALL}")
            for r in res["rewards"]:
                print(f"  • {r['name']} ×{r['amount']}")


GameApplication.run = patched_run
muforge.CLASSES["application"] = GameApplication

if __name__ == "__main__":
    asyncio.run(run_program("game", settings))
