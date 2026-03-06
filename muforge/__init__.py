import typing
import uuid
from collections import defaultdict

SETTINGS = dict()
APP = None
PLUGINS: dict[str, "BasePlugin"] = dict()
PLUGIN_PATHS = list()
CLASSES = dict()
SSL_CONTEXT = None
SERVICES = dict()
EVENTS = dict()
LOCKPARSER = None
PGPOOL = None
EVENT_HUB = None
LOCKFUNCS = dict()
LISTENERS = dict()
LISTENERS_TABLE = dict()

PORTAL_COMMANDS = dict()
PORTAL_COMMANDS_PRIORITY = defaultdict(list)

USER_COMMANDS = dict()
USER_COMMANDS_PRIORITY = defaultdict(list)

PC_COMMANDS = dict()
PC_COMMANDS_PRIORITY = defaultdict(list)

PC_SESSIONS: dict[uuid.UUID, "PCSession"] = dict()
USER_SESSIONS: dict[uuid.UUID, "UserSession"] = dict()
