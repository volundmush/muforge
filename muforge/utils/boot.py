import sys
import ssl
import os
import asyncio

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


async def setup_program(program: str, settings: dict):

    if not Path("logs").exists():
        raise FileNotFoundError(
            "logs folder not found in current directory! Are you sure you're in the right place?"
        )
    setup_logging(program)

    cert = settings.get("TLS", dict()).get("certificate", None)
    key = settings.get("TLS", dict()).get("key", None)
    if cert and key and Path(cert).exists() and Path(key).exists():
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert, key)
        muforge.SSL_CONTEXT = context

    for k, v in settings[program.upper()].get("classes", dict()).items():
        muforge.CLASSES[k] = property_from_module(v)


async def run_program(program: str, settings: dict):
    import muforge

    muforge.SETTINGS.update(settings)

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
            app_class = muforge.CLASSES["application"]
            app = app_class()
            muforge.APP = app
            await app.setup()
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

    files = [root_path / "default.toml"]

    # Instead of fixed names, find all framework config files matching
    # the pattern in the current working directory.
    # If you name them as config.framework-001.toml, config.framework-002.toml, etc.,
    # a lexicographical sort should work reliably.
    plugin_files = sorted(Path.cwd().glob("plugin-*.toml"))
    files.extend(plugin_files)

    for f in (
        "user",
        f"user-{mode}",
        "secrets",
        f"secrets-{mode}",
    ):
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
    try:
        from uvloop import run
    except ImportError:
        from asyncio import run
    run(main(mode), debug=True)
