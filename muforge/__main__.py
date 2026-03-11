import asyncio

from .utils.boot import get_config
from .utils.misc import property_from_module

config = get_config("launcher")
launch_class = property_from_module(config["MUFORGE"]["launcher"])

launcher = launch_class(config)

asyncio.run(launcher.run())
