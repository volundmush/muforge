import asyncio
import aiodns
import sys
import traceback
from loguru import logger

from mudpy import Application as _Application

class Application(_Application):
    name = "game"
