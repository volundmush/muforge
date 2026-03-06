import asyncio
import os
import typing
from collections import defaultdict
from uuid import UUID

from dotenv import load_dotenv

import muforge
from rhost import Database, MushAttribute, MushObject, ObjectType, parse_flatfile

ACCOUNTS_MUSH: dict[int, MushObject] = dict()
ACCOUNTS_MAP: dict[int, UUID] = dict()
ACCOUNTS_CHARACTERS: dict[int, list[MushObject]] = defaultdict(list)
ACCOUNTS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)

CHARACTERS_MUSH: dict[int, MushObject] = dict()
CHARACTERS_MAP: dict[int, UUID] = dict()
CHARACTERS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)
CHARACTERS_ACCOUNT: dict[int, MushObject] = dict()

BOARDS_MUSH: dict[int, MushObject] = dict()
BOARDS_MAP: dict[int, UUID] = dict()
BOARDS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)

FACTIONS_MUSH: dict[int, MushObject] = dict()
FACTIONS_MAP: dict[int, UUID] = dict()
FACTIONS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)

THEMES_MUSH: dict[int, MushObject] = dict()
THEMES_MAP: dict[int, UUID] = dict()
THEMES_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)


async def prepare_accounts(db: Database):
    accounts = db.contents("#acc")
    for account in accounts:
        ACCOUNTS_MUSH[account.dbref] = account
        characters = list()
        if char_attr := db.get(account, "CHARACTERS"):
            characters.extend(
                [c for x in char_attr.split() if (c := db._ensure_obj(x))]
            )
        ACCOUNTS_CHARACTERS[account.dbref] = characters
        for char in characters:
            CHARACTERS_MUSH[char.dbref] = char
            CHARACTERS_ACCOUNT[char.dbref] = account
        admin_level = max([c.bitlevel for c in characters]) if characters else 0
        password = db.get(account, "_PASSWORD")
        name = account.name
        email = None

        if "@" in account.name:
            email = account.name
            name = account.name.split("@")[0]

        ACCOUNTS_DATA[account.dbref] = {
            "admin_level": admin_level,
            "password": password,
            "name": name,
            "email": email,
        }


async def prepare_pcs(db: Database):
    for k, v in ACCOUNTS_CHARACTERS.items():
        account = db._ensure_obj(k)
        for char in v:
            approved = None
            if app_text := db.get(char, "GAME.APPROVED"):
                approved = int(app_text)

            CHARACTERS_DATA[char.dbref] = {
                "name": char.name,
                "approved": approved,
                "user": account,
            }


async def prepare_factions(db: Database):
    fparent = db._ensure_obj("#fac_parent")
    factions = db.contents(fparent)
    for faction in factions:
        FACTIONS_MUSH[faction.dbref] = faction

        fac_mem_key = faction.objid.replace(":", "_")

        rank_attrs = db.lattr(faction, "RANK.*", inherit=True)

        rank_nums = {int(key.split(".")[1]) for key, attr in rank_attrs.items()}

        rank_data: dict[int, dict] = defaultdict(dict)

        for key, attr in rank_attrs.items():
            split = key.split(".")
            num = int(split[1])
            key2 = split[2]

            match key2:
                case "PERM":
                    rank_data[num]["permissions"] = attr.upper().split()
                case _:
                    rank_data[num][key2.lower()] = attr

        for num in rank_nums:
            members = db.get(faction, f"MEMBERS.{num}", inherit=True) or ""
            member_objids = [
                db._ensure_obj(oid) for oid in (members.split() if members else [])
            ]

            member_data = defaultdict(dict)
            for member in member_objids:
                if title := db.get(member, f"FAC.{fac_mem_key}.TITLE", inherit=True):
                    member_data[member]["title"] = title
                if permissions := db.get(
                    member, f"FAC.{fac_mem_key}.PERMISSIONS", inherit=True
                ):
                    member_data[member]["permissions"] = permissions.upper().split()
            rank_data[num]["members"] = member_data

        FACTIONS_DATA[faction.dbref] = {
            "name": faction.name,
            "ranks": rank_data,
        }
        if fac_perm := db.get(faction, "CONFIG.ALLPERM.VALUE"):
            FACTIONS_DATA[faction.dbref]["permissions"] = fac_perm.upper().split()


async def prepare_boards(db: Database):
    pass


async def prepare_themes(db: Database):
    pass


async def prepare():
    data = parse_flatfile("netrhost.db.flat")
    await prepare_accounts(data)
    await prepare_pcs(data)
    await prepare_factions(data)

    return data


async def main():
    # do a basic setup of the game in order to init postgres
    from muforge.shared.utils import get_config, setup_program

    config = get_config("game")
    await setup_program("game", config)
    app_class = muforge.CLASSES["application"]
    app = app_class()
    muforge.APP = app
    await app.setup()

    db = await prepare()


if __name__ == "__main__":
    asyncio.run(main())
