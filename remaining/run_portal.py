import asyncio

import muforge
from dynaconf import Dynaconf
from muforge.portal.application import Application as PortalApplication
from muforge.shared.utils import run_program

# minimal settings for the portal
settings = Dynaconf(
    environments=True,
    settings_files=[],
    envvar_prefix=False,
)

# portal app expects SETTINGS["PORTAL"]["commands"]
settings.set("PORTAL", {
    "commands": {}  # empty is fine
})

# register portal app manually
muforge.CLASSES["application"] = PortalApplication

asyncio.run(run_program("portal", settings))
