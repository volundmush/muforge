from muforge.fastapi import create_app
from muforge.utils import get_config

from .router import router as identity_router

config = get_config("auth")


app_config = {
    "title": f"{config['MSSP']['NAME']} Identity",
}

app = create_app("auth", app_config, config)
app.include_router(identity_router, prefix="/auth")
