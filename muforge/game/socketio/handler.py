import asyncio
import muforge

from muforge.shared.utils import class_from_module

class SocketIOHandler:

    def __init__(self, sio):
        self.sio = sio
        self.handlers = dict()

    async def setup(self):
        for k, v in muforge.SETTINGS["GAME"]["socketio_events"].items():
            c = class_from_module(v)
            self.sio.on(k, c)
            self.handlers[k] = c