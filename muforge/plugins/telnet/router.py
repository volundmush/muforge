import psutil
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class MSSPResponse(BaseModel):
    data: tuple[tuple[str, str], ...] = Field(default_factory=lambda: ())


router = APIRouter()

PROCESS = None


@router.get("/mssp", response_model=MSSPResponse)
async def get_mssp(request: Request):
    """
    Returns the MSSP response for the telnet server.

    Reference: https://mudstandards.org/mud/mssp
    """
    app = request.app.state.application
    plugin = app.plugins["telnet"]
    overrides = plugin.settings.get("mssp", dict()).copy()

    global PROCESS
    if PROCESS is None:
        PROCESS = psutil.Process()

    # order does matter for this.
    output: list[tuple[str, str]] = list()
    if ovr := overrides.pop("NAME", None):
        output.append(("NAME", ovr))
    else:
        output.append(("NAME", app.complete_settings.get("NAME", "MuForge")))

    # This should not be overriden. That'd be a lie!
    if ovr := overrides.pop("PLAYERS", None) is not None:
        output.append(("PLAYERS", str(ovr)))
    else:
        output.append(("PLAYERS", str(len(app.active_sessions))))

    # Likewise with UPTIME...
    # This should not be overriden. That'd be a lie!
    if ovr := overrides.pop("UPTIME", None) is not None:
        output.append(("UPTIME", str(int(ovr))))
    else:
        output.append(("UPTIME", str(int(PROCESS.create_time()))))

    # CHARSETS
    if ovr := overrides.pop("CHARSETS", None):
        output.append(("CHARSETS", ovr))
    else:
        output.append(("CHARSETS", "ascii utf-8"))

    # CODEBASE
    if ovr := overrides.pop("CODEBASE", None):
        output.append(("CODEBASE", ovr))
    else:
        output.append(("CODEBASE", "muforge"))

    # CRAWL DELAY
    if ovr := overrides.pop("CRAWL DELAY", None):
        output.append(("CRAWL DELAY", str(ovr)))
    else:
        output.append(("CRAWL DELAY", "-1"))

    # PORT
    if ovr := overrides.pop("PORT", None):
        output.append(("PORT", str(ovr)))
    else:
        if srv := app.services.get("telnet", None):
            output.append(("PORT", str(srv.port)))

    # SSL
    if ovr := overrides.pop("SSL", None):
        output.append(("SSL", ovr))
    else:
        if srv := app.services.get("telnets", None):
            output.append(("SSL", str(srv.port)))

    # PROTOCOLS SECTION
    # ANSI
    if ovr := overrides.pop("ANSI", None):
        output.append(("ANSI", ovr))
    else:
        output.append(("ANSI", "1"))

    # UTF-8
    if ovr := overrides.pop("UTF-8", None):
        output.append(("UTF-8", ovr))
    else:
        output.append(("UTF-8", "1"))

    # XTERM 256 COLORS
    if ovr := overrides.pop("XTERM 256 COLORS", None):
        output.append(("XTERM 256 COLORS", ovr))
    else:
        output.append(("XTERM 256 COLORS", "1"))

    # XTERM TRUE COLORS
    if ovr := overrides.pop("XTERM TRUE COLORS", None):
        output.append(("XTERM TRUE COLORS", ovr))
    else:
        output.append(("XTERM TRUE COLORS", "1"))

    # From here on out, we need to add any remaining overrides as-is
    for key, value in overrides.items():
        output.append((key.upper(), value))

    return MSSPResponse(data=tuple(output))
