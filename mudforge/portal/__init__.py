#!/usr/bin/env python
import asyncio
import mudforge
from mudforge.utils import run_program, get_config


if __name__ == "__main__":
    settings = get_config("portal")
    asyncio.run(run_program("portal", settings), debug=True)
