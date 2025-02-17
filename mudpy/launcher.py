#!/usr/bin/env python
import sys
import shutil
import pathlib
import asyncio
from mudpy.utils import class_from_module, get_config
import mudpy
from pathlib import Path


def main():
    root_dir = pathlib.Path(mudpy.__file__).parent
    temp_location = root_dir / "template"

    # first we'll check to see if a config file exists...
    if not Path("config.default.toml").exists():
        """
        If the config file doesn't exist, we'll check sys.args to see if the user
        is trying to create a new project folder via "mudlib init <dir>"
        """
        if len(sys.argv) > 1 and sys.argv[1].lower().strip() == "init":
            # now we need to check if we have a dirname, and only if it doesn't
            # already exist do we copy the template folder to the new location
            if len(sys.argv) > 2:
                new_dir = Path(sys.argv[2])
                if not new_dir.exists():
                    shutil.copytree(temp_location, new_dir)
                    print(f"Created new project folder: {new_dir}")
                else:
                    print(f"Error: {new_dir} already exists.")
            else:
                print("Error: No directory name provided.")
            return
        else:
            print("Error: No config file found. Are you in the right directory?")
            print("To create a new project directory, use 'mudlib init <dir>'")
            return

    d = get_config("")
    launcher_class = class_from_module(d["SHARED"]["launcher"])
    launcher = launcher_class(d)
    asyncio.run(launcher.run())

if __name__ == "__main__":
    main()