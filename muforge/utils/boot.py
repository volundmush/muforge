import asyncio
import os
import signal
import ssl
import sys
from pathlib import Path

from loguru import logger

import muforge

from .misc import property_from_module


def setup_logging(name: str):

    logformat = {
        "format": "{time} - {level} - {message}",
        "backtrace": True,
        "diagnose": True,
    }

    config = {
        "handlers": [
            {"sink": sys.stdout, "colorize": True, **logformat},
            {
                "sink": f"logs/{name}.log",
                "serialize": True,
                "compression": "zip",
                **logformat,
            },
        ],
    }
    logger.configure(**config)


def install_signal_handlers(app):
    def _handle_signal(sig):
        logger.info(f"Received signal {sig.name}, shutting down...")
        app.shutdown()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError, RuntimeError:
            signal.signal(sig, lambda *_: _handle_signal(sig))


async def setup_program(program: str, settings: dict):

    if not Path("logs").exists():
        raise FileNotFoundError(
            "logs folder not found in current directory! Are you sure you're in the right place?"
        )
    setup_logging(program)


async def run_program(program: str, settings: dict):

    pidfile = Path(f"{program}.pid")
    if pidfile.exists():
        with open(pidfile, "r") as f:
            pid = f.read().strip()
        if os.path.exists(f"/proc/{pid}"):
            # If the pidfile exists and the process is still running, we raise an error.
            raise FileExistsError(
                f"{pidfile} already exists! Is the {program} already running? (PID: {pid})"
            )
        else:
            # If the pidfile exists but the process is not running, we remove the pidfile.
            logger.warning(f"Removing stale pidfile {pidfile} for {program}.")
            pidfile.unlink(missing_ok=True)

    await setup_program(program, settings)

    try:
        with open(pidfile, "w") as f:
            f.write(str(os.getpid()))
            f.flush()
            app_class = property_from_module(
                settings[program.upper()].get("class", None)
            )
            app = app_class(settings)
            await app.setup()
            install_signal_handlers(app)
            try:
                await app.run()
            except asyncio.CancelledError:
                logger.info("App run finished")
                app.shutdown()
    finally:
        pidfile.unlink(missing_ok=True)


def get_config(mode: str) -> dict:
    from dynaconf import Dynaconf

    root_path = Path.cwd() / "config"
    files = list()

    for x in ("muforge", "game", "portal"):
        config_path = root_path / f"{x}.toml"
        if config_path.exists():
            files.append(config_path)

    # Instead of fixed names, find all framework config files matching
    # the pattern in the current working directory.
    # If you name them as config.framework-001.toml, config.framework-002.toml, etc.,
    # a lexicographical sort should work reliably.
    plugin_files = sorted(root_path.glob("plugin-*.toml"))
    files.extend(plugin_files)

    for f in ("secrets",):
        config_path = root_path / f"{f}.toml"
        if config_path.exists():
            files.append(config_path)

    d = Dynaconf(settings_files=files)

    return d.to_dict()


async def main(mode: str):
    settings = get_config(mode)
    await run_program(mode, settings)


def startup(mode: str):
    run = None
    from asyncio import run

    run(main(mode), debug=True)
