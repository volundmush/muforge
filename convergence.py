import asyncio
import os
import typing
from collections import defaultdict

from dotenv import load_dotenv

from rhost import Database, MushAttribute, MushObject, ObjectType, parse_flatfile

ACCOUNTS_MUSH: dict[int, MushObject] = dict()
ACCOUNTS_RECORD: dict[int, str] = dict()
ACCOUNTS_CHARACTERS: dict[int, list[MushObject]] = defaultdict(list)
ACCOUNTS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)

CHARACTERS_MUSH: dict[int, MushObject] = dict()
CHARACTERS_RECORD: dict[int, str] = dict()
CHARACTERS_DATA: dict[int, dict[str, typing.Any]] = defaultdict(dict)
CHARACTERS_ACCOUNT: dict[int, MushObject] = dict()


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
        password = db.get(account, "PASSWORD")
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
        acc_rec = ACCOUNTS_RECORD.get(k)
        for char in v:
            approved = None
            if app_text := db.get(char, "GAME.APPROVED"):
                approved = int(app_text)

            CHARACTERS_DATA[char.dbref] = {
                "name": char.name,
                "approved": approved,
                "user": acc_rec,
            }


async def main():
    load_dotenv()
    data = parse_flatfile("netrhost.db.flat")
    await prepare_accounts(data)
    await prepare_pcs(data)

    db = AsyncSurreal(f"ws://localhost:{os.getenv('SURREALDB_PORT')}")

    await db.signin(
        {"user": os.getenv("SURREAL_USER"), "pass": os.getenv("SURREAL_PASS")}
    )
    await db.use(
        os.getenv("SURREAL_DEFAULT_NAMESPACE"), os.getenv("SURREAL_DEFAULT_DATABASE")
    )


if __name__ == "__main__":
    asyncio.run(main())
