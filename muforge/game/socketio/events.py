import pydantic
import muforge

async def connect(sid, environ, auth):
    pass

async def disconnect(sid, reason):
    pass

async def any(sid, data):
    print(sid, data)