#!/usr/bin/env python
import asyncio
from muforge.shared.utils import run_program, get_config


async def main():
    settings = get_config("game")
    await run_program("game", settings)


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
