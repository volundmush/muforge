#!/usr/bin/env python
import asyncio
import mudpy
from mudpy.utils import run_program, get_config


if __name__ == "__main__":
    settings = get_config("portal")
    asyncio.run(run_program("portal", settings), debug=True)
