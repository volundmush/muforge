from collections import defaultdict

SETTINGS = dict()
APP = None
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

GAME_COMMANDS = dict()
GAME_COMMANDS_PRIORITY = defaultdict(list)

LOCATIONS = dict()
LOCATION_CLASSES = dict()
LOCATION_COMPONENTS = dict()

ENTITIES = dict()
ENTITY_CLASSES = dict()
ENTITY_COMPONENTS = dict()

ENTITY_TYPE_INDEX = defaultdict(set)

ATTRIBUTES = dict()
NODES = dict()
ROOMS = dict()
