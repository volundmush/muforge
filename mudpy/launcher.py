#!/usr/bin/env python
import sys
import os
import shutil
import pathlib
import asyncio
import argparse
from mudpy.utils import class_from_module
import mudpy

class Launcher:
    root_dir = pathlib.Path(mudpy.__file__).parent

    def __init__(self):
        self.parser = self._get_parser()
        self.cmd_args = self.parser.parse_args()

    def _get_parser(self):
        parser = argparse.ArgumentParser(
            prog="mudpy",
            description="MUDPy Launcher - Manage MUD projects and services."
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        # --- "init" command ------------------------------------------
        init_parser = subparsers.add_parser("init",
                                            help="Initialize a new MUD project in the specified directory."
                                            )
        init_parser.add_argument(
            "directory",
            help="Directory where the new project will be created/copied."
        )
        # (Optionally add more flags for 'init', e.g. template selection)

        # --- "start" command -----------------------------------------
        start_parser = subparsers.add_parser("start",
                                             help="Start a specified component/service (e.g. portal, server)."
                                             )
        start_parser.add_argument(
            "component",
            help="Name of the component to start (e.g. 'portal', 'server')."
        )
        # Possibly add optional arguments here, like config paths, ports, etc.

        # --- "status" command ----------------------------------------
        status_parser = subparsers.add_parser("status",
                                              help="Check the status of a specified component."
                                              )
        status_parser.add_argument(
            "component",
            help="Name of the component to query status for."
        )

        # --- "stop" command ------------------------------------------
        stop_parser = subparsers.add_parser("stop",
                                            help="Stop a specified component/service."
                                            )
        stop_parser.add_argument(
            "component",
            help="Name of the component to stop."
        )

        return parser


    async def run(self):

        match self.cmd_args.command.lower():
            case "init":
                await self.do_init()
            case "start":
                await self.do_start()
            case "status":
                await self.do_status()
            case "stop":
                await self.do_stop()
            case _:
                print("Invalid command.")
                self.parser.print_help()

    async def run_init(self):
        """
        Initialize a new MUD project in the specified directory.

        This needs to check the user input (which needs to be evaluated as a path),
        then copy the project template to the specified directory.

        The project template is located at self.root_dir / "template".

        If the destination directory already exists, abort with an error.
        """
        temp_location = self.root_dir / "template"
        dest_location = pathlib.Path(self.cmd_args.directory)

        if dest_location.exists():
            print(f"Error: Destination directory '{dest_location}' already exists.")
            return

        print(f"Copying project template from '{temp_location}' to '{dest_location}'...")
        # Copy the template to the destination directory.
        shutil.copytree(temp_location, dest_location)
        os.rename(dest_location / "gitignore", dest_location / ".gitignore")

    async def is_running(self, component: str) -> bool:
        """
        We need to check if the specified component is running.
        We can do this by looking at <cwd>/<component>.pid and seeing what's going on.
        """
        pid_file = pathlib.Path(f"{component}.pid")
        if not pid_file.exists():
            return False
        with open(pid_file) as f:
            pid = int(f.read())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Stale pidfile so remove it.
            print(f"Removing stale pidfile '{pid_file}'...")
            os.remove(pid_file)
            return False
        return True

    async def run_start(self):
        arg = self.cmd_args.component.lower()
        if arg not in ["portal", "game"]:
            print(f"Error: Invalid component '{arg}'.")
            return

    async def run_status(self):
        arg = self.cmd_args.component.lower()
        if arg not in ["portal", "game"]:
            print(f"Error: Invalid component '{arg}'.")
            return
        if await self.is_running(arg):
            print(f"{arg.capitalize()} is running.")
        else:
            print(f"{arg.capitalize()} is not running.")

    async def run_stop(self):
        arg = self.cmd_args.component.lower()
        if arg not in ["portal", "game"]:
            print(f"Error: Invalid component '{arg}'.")
            return

def main():
    launcher = Launcher()
    asyncio.run(launcher.run())


if __name__ == "__main__":
    main()