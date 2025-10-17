import importlib
import uuid
import typing
import random
import string
import re
import os
import types
import traceback
import time
import sys
import ssl
from pathlib import Path
import argparse
import signal
import asyncio
from contextlib import asynccontextmanager
from passlib.context import CryptContext
from collections import defaultdict

from datetime import datetime, timezone
from inspect import getmembers, getmodule, getmro, ismodule, trace

from loguru import logger

crypt_context = CryptContext(schemes=["argon2"])


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
    import mudforge

    mudforge.SETTINGS.update(settings)

    if not Path("logs").exists():
        raise FileNotFoundError(
            "logs folder not found in current directory! Are you sure you're in the right place?"
        )
    setup_logging(program)

    cert = settings["TLS"].get("certificate", None)
    key = settings["TLS"].get("key", None)
    if cert and key and Path(cert).exists() and Path(key).exists():
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert, key)
        mudforge.SSL_CONTEXT = context

    for k, v in settings[program.upper()].get("classes", dict()).items():
        mudforge.CLASSES[k] = class_from_module(v)


async def run_program(program: str, settings: dict):
    import mudforge

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
            app_class = mudforge.CLASSES["application"]
            app = app_class()
            mudforge.APP = app
            await app.setup()
            try:
                await app.run()
            except asyncio.CancelledError:
                logger.info("App run finished")
                app.shutdown()
    finally:
        pidfile.unlink(missing_ok=True)


def get_config(mode: str) -> dict:
    import mudforge
    from dynaconf import Dynaconf

    root_path = Path(mudforge.__file__).parent

    files = [root_path / "config.default.toml"]

    # Instead of fixed names, find all framework config files matching
    # the pattern in the current working directory.
    # If you name them as config.framework-001.toml, config.framework-002.toml, etc.,
    # a lexicographical sort should work reliably.
    plugin_files = sorted(Path.cwd().glob("config.plugin-*.toml"))
    files.extend(plugin_files)

    for f in (
        "user",
        f"user-{mode}",
        "secrets",
        f"secrets-{mode}",
    ):
        if Path(f"config.{f}.toml").exists():
            files.append(f"config.{f}.toml")

    d = Dynaconf(settings_files=files)

    return d.to_dict()


def utcnow():
    return datetime.now(timezone.utc)


def import_from_module(path: str) -> typing.Any:
    if not path:
        raise ImportError("Cannot import null path!")
    if "." not in path:
        raise ImportError("Path is not in dot format!")
    split_path = path.split(".")
    identifier = split_path.pop(-1)
    module = importlib.import_module(".".join(split_path))
    return getattr(module, identifier)


def mod_import_from_path(path):
    """
    Load a Python module at the specified path.

    Args:
        path (str): An absolute path to a Python module to load.

    Returns:
        (module or None): An imported module if the path was a valid
        Python module. Returns `None` if the import failed.

    """
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    dirpath, filename = path.rsplit(os.path.sep, 1)
    modname = filename.rstrip(".py")

    try:
        return importlib.machinery.SourceFileLoader(modname, path).load_module()
    except OSError:
        logger.error(
            f"Could not find module '{modname}' ({modname}.py) at path '{dirpath}'"
        )
        return None


def mod_import(module):
    """
    A generic Python module loader.

    Args:
        module (str, module): This can be either a Python path
            (dot-notation like `evennia.objects.models`), an absolute path
            (e.g. `/home/eve/evennia/evennia/objects/models.py`) or an
            already imported module object (e.g. `models`)
    Returns:
        (module or None): An imported module. If the input argument was
        already a module, this is returned as-is, otherwise the path is
        parsed and imported. Returns `None` and logs error if import failed.

    """
    if not module:
        return None

    if isinstance(module, types.ModuleType):
        # if this is already a module, we are done
        return module

    if module.endswith(".py") and os.path.exists(module):
        return mod_import_from_path(module)

    try:
        return importlib.import_module(module)
    except ImportError:
        return None


def callables_from_module(module) -> dict[str, callable]:
    """
    Return all global-level callables defined in a module.

    Args:
        module (str, module): A python-path to a module or an actual
            module object.

    Returns:
        callables (dict): A dict of {name: callable, ...} from the module.

    Notes:
        Will ignore callables whose names start with underscore "_".

    """
    mod = mod_import(module)
    if not mod:
        return {}
    # make sure to only return callables actually defined in this module (not imports)
    members = getmembers(
        mod, predicate=lambda obj: callable(obj) and getmodule(obj) == mod
    )
    return dict((key, val) for key, val in members if not key.startswith("_"))


# to_str is yoinked from Evennia.
def to_str(text, session=None):
    """
    Try to decode a bytestream to a python str, using encoding schemas from settings
    or from Session. Will always return a str(), also if not given a str/bytes.

    Args:
        text (any): The text to encode to bytes. If a str, return it. If also not bytes, convert
            to str using str() or repr() as a fallback.
        session (Session, optional): A Session to get encoding info from. Will try this before
            falling back to settings.ENCODINGS.

    Returns:
        decoded_text (str): The decoded text.

    Note:
        If `text` is already str, return it as is.
    """
    if isinstance(text, str):
        return text
    if not isinstance(text, bytes):
        # not a byte, convert directly to str
        try:
            return str(text)
        except Exception:
            return repr(text)

    default_encoding = (
        session.protocol_flags.get("ENCODING", "utf-8") if session else "utf-8"
    )
    try:
        return text.decode(default_encoding)
    except (LookupError, UnicodeDecodeError):
        for encoding in ["utf-8", "latin-1", "ISO-8859-1"]:
            try:
                return text.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                pass
        # no valid encoding found. Replace unconvertable parts with ?
        return text.decode(default_encoding, errors="replace")


def inherits_from(obj, parent):
    """
    Takes an object and tries to determine if it inherits at *any*
    distance from parent.

    Args:
        obj (any): Object to analyze. This may be either an instance or
            a class.
        parent (any): Can be either an instance, a class or the python
            path to the class.

    Returns:
        inherits_from (bool): If `parent` is a parent to `obj` or not.

    Notes:
        What differentiates this function from Python's `isinstance()` is the
        flexibility in the types allowed for the object and parent being compared.

    """

    if callable(obj):
        # this is a class
        obj_paths = ["%s.%s" % (mod.__module__, mod.__name__) for mod in obj.mro()]
    else:
        obj_paths = [
            "%s.%s" % (mod.__module__, mod.__name__) for mod in obj.__class__.mro()
        ]

    if isinstance(parent, str):
        # a given string path, for direct matching
        parent_path = parent
    elif callable(parent):
        # this is a class
        parent_path = "%s.%s" % (parent.__module__, parent.__name__)
    else:
        parent_path = "%s.%s" % (parent.__class__.__module__, parent.__class__.__name__)
    return any(1 for obj_path in obj_paths if obj_path == parent_path)


def is_iter(obj):
    """
    Checks if an object behaves iterably.

    Args:
        obj (any): Entity to check for iterability.

    Returns:
        is_iterable (bool): If `obj` is iterable or not.

    Notes:
        Strings are *not* accepted as iterable (although they are
        actually iterable), since string iterations are usually not
        what we want to do with a string.

    """
    if isinstance(obj, (str, bytes)):
        return False

    try:
        return iter(obj) and True
    except TypeError:
        return False


def make_iter(obj):
    """
    Makes sure that the object is always iterable.

    Args:
        obj (any): Object to make iterable.

    Returns:
        iterable (list or iterable): The same object
            passed-through or made iterable.

    """
    return not is_iter(obj) and [obj] or obj


# lazy load handler
_missing = object()


# Lazy property yoinked from evennia
class lazy_property:
    """
    Delays loading of property until first access. Credit goes to the
    Implementation in the werkzeug suite:
    http://werkzeug.pocoo.org/docs/utils/#werkzeug.utils.cached_property

    This should be used as a decorator in a class and in Evennia is
    mainly used to lazy-load handlers:

        ```python
        @lazy_property
        def attributes(self):
            return AttributeHandler(self)
        ```

    Once initialized, the `AttributeHandler` will be available as a
    property "attributes" on the object.

    """

    def __init__(self, func, name=None, doc=None):
        """Store all properties for now"""
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        """Triggers initialization"""
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
        obj.__dict__[self.__name__] = value
        return value


def fresh_uuid4(existing) -> uuid:
    """
    Given a list of UUID4s, generate a new one that's not already used.
    Yes, I know this is silly. UUIDs are meant to be unique by sheer statistic unlikelihood of a conflict.
    I'm just that afraid of collisions.
    """
    existing = set(existing)
    fresh_uuid = uuid.uuid4()
    while fresh_uuid in existing:
        fresh_uuid = uuid.uuid4()
    return fresh_uuid


def partial_match(
    match_text: str,
    candidates: typing.Iterable[typing.Any],
    key: callable = str,
    exact: bool = False,
    many_results: bool = False,
) -> typing.Optional[typing.Any]:
    """
    Given a list of candidates and a string to search for, does a case-insensitive partial name search against all
    candidates, preferring exact matches.

    Args:
        match_text (str): The string being searched for.
        candidates (list of obj): A list of any kind of object that key can turn into a string to search.
        key (callable): A callable that must return a string, used to do the search. this 'converts' the objects in the
            candidate list to strings.
        exact (bool): If True, only exact matches are returned.
        many_results (bool): If True, returns a list of all matches. If False, returns the first match.


    Returns:
        Any or None, or a list[Any]
    """
    mlow = match_text.lower()
    out = list()

    candidates_sorted = sorted((key(c).lower(), c) for c in candidates)

    for can_lower, candidate in candidates_sorted:
        if mlow == can_lower:
            if many_results:
                out.append(candidate)
            else:
                return candidate
        elif not exact and can_lower.startswith(mlow):
            if many_results:
                out.append(candidate)
            else:
                return candidate
    return out if many_results else None


def generate_name(prefix: str, existing, gen_length: int = 20) -> str:
    def gen():
        return f"{prefix}_{''.join(random.choices(string.ascii_letters + string.digits, k=gen_length))}"

    while (u := gen()) not in existing:
        return u


def get_server_pid() -> typing.Optional[int]:
    try:
        f = open("game_code.pid", mode="r")
        pid = int(f.read())
        return pid
    except:
        return None


def iequals(first: str, second: str):
    return str(first).lower() == str(second).lower()


RE_STAT_NAME = re.compile(r"^[a-zA-Z0-9_ \-,.']+$")


def validate_name(
    name: str,
    thing_type: str = "Stat",
    matcher=RE_STAT_NAME,
    ex_type: Exception = ValueError,
) -> str:
    """
    Cleans and validates a stat name for use in the system.
    This should strip/trim leading/trailing spaces and squish double spaces
    and only allow certain characters.

    Args:
        name (str): The input value.
        thing_type (str): The name of the type of thing being provided. used for errors.
        matcher (regex): The regex to match against.

    Returns:
        str: The cleaned name.

    Raises:
        ValueError: With the error message.
    """
    name = name.strip()
    # remove all double-spaces.
    while "  " in name:
        name = name.replace("  ", " ")
    if not name:
        raise ex_type(f"{thing_type} name cannot be empty.")
    if not matcher.match(name):
        raise ex_type(f"{thing_type} contains forbidden characters.")
    return name


class classproperty(property):
    """
    Decorator class which combines @property and @classmethod.

    It does exactly what you'd expect those two decorators combined would do.
    """

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


def class_from_module(path, defaultpaths=None, fallback=None):
    """
    Return a class from a module, given the class' full python path. This is
    primarily used to convert db_typeclass_path:s to classes.

    Args:
        path (str): Full Python dot-path to module.
        defaultpaths (iterable, optional): If a direct import from `path` fails,
            try subsequent imports by prepending those paths to `path`.
        fallback (str): If all other attempts fail, use this path as a fallback.
            This is intended as a last-resort. In the example of Evennia
            loading, this would be a path to a default parent class in the
            evennia repo itself.

    Returns:
        class (Class): An uninstantiated class recovered from path.

    Raises:
        ImportError: If all loading failed.

    """

    cls = None
    err = ""
    if defaultpaths:
        paths = (
            [path] + ["%s.%s" % (dpath, path) for dpath in make_iter(defaultpaths)]
            if defaultpaths
            else []
        )
    else:
        paths = [path]

    for testpath in paths:
        if "." in path:
            testpath, clsname = testpath.rsplit(".", 1)
        else:
            raise ImportError(
                "the path '%s' is not on the form modulepath.Classname." % path
            )

        try:
            if not importlib.util.find_spec(testpath, package="evennia"):
                continue
        except ModuleNotFoundError:
            continue

        try:
            mod = importlib.import_module(testpath, package="evennia")
        except ModuleNotFoundError:
            err = traceback.format_exc(30)
            break

        try:
            cls = getattr(mod, clsname)
            break
        except AttributeError:
            if len(trace()) > 2:
                # AttributeError within the module, don't hide it
                err = traceback.format_exc(30)
                break
    if not cls:
        err = "\nCould not load typeclass '{}'{}".format(
            path, " with the following traceback:\n" + err if err else ""
        )
        if defaultpaths:
            err += "\nPaths searched:\n    %s" % "\n    ".join(paths)
        else:
            err += "."
        logger.error(err)
        if fallback:
            logger.warning(f"Falling back to {fallback}.")
            return class_from_module(fallback)
        else:
            # even fallback fails
            raise ImportError(err)
    return cls


# alias
object_from_module = class_from_module


class LogTime:
    def __init__(self, message, level="INFO"):
        """
        :param message: The message to log (e.g. "Loading map")
        :param level: The log level (TRACE, DEBUG, INFO, etc.)
        """
        self.message = message
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        duration = end_time - self.start_time
        logger.log(self.level, f"{self.message} took {duration:.6f} seconds")


class Launcher:
    import mudforge

    root_dir = Path(mudforge.__file__).parent
    components = ["portal", "game"]

    def __init__(self, settings: dict):
        self.settings = settings
        self.parser = self._get_parser()
        self.command_subparsers = None
        self.cmd_args = self.parser.parse_args()

    def _get_parser(self):
        parser = argparse.ArgumentParser(
            prog="muforge",
            description="muforge Launcher - Manage MUD projects and services.",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)
        self.command_subparsers = subparsers

        # --- "start" command -----------------------------------------
        start_parser = subparsers.add_parser(
            "start", help="Start a specified component/service (e.g. portal, server)."
        )
        start_parser.add_argument(
            "component",
            help="Name of the component to start (e.g. 'portal', 'server').",
        )
        # Possibly add optional arguments here, like config paths, ports, etc.

        # --- "status" command ----------------------------------------
        status_parser = subparsers.add_parser(
            "status", help="Check the status of a specified component."
        )
        status_parser.add_argument(
            "component", help="Name of the component to query status for."
        )

        # --- "stop" command ------------------------------------------
        stop_parser = subparsers.add_parser(
            "stop", help="Stop a specified component/service."
        )
        stop_parser.add_argument("component", help="Name of the component to stop.")

        return parser

    async def run(self):
        try:
            if func := getattr(self, f"do_{self.cmd_args.command}"):
                await func()
            else:
                print("Invalid command.")
                self.parser.print_help()
        except Exception as e:
            print(f"Error: {e}")

    async def is_running(self, component: str) -> bool:
        """
        We need to check if the specified component is running.
        We can do this by looking at <cwd>/<component>.pid and seeing what's going on.
        """
        pid_file = Path(f"{component}.pid")
        if not pid_file.exists():
            return False
        with open(pid_file) as f:
            pid = int(f.read())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Stale pidfile so remove it.
            print(f"Removing stale pidfile '{pid_file}'...")
            os.remove(pid_file)
            return False
        return True

    def check_component(self, component: str) -> str:
        lowered = component.lower().strip()
        if component.lower().strip() not in self.components:
            raise ValueError(
                f"Error: Invalid component '{component}'. Valid choices: {', '.join(self.components)}"
            )
        return lowered

    async def run_start(self):
        component = self.check_component(self.cmd_args.component)

    async def run_status(self):
        component = self.check_component(self.cmd_args.component)
        if await self.is_running(component):
            print(f"{component.capitalize()} is running.")
        else:
            print(f"{component.capitalize()} is not running.")

    async def run_stop(self):
        component = self.check_component(self.cmd_args.component)


class Broadcaster:
    def __init__(self):
        self._subscribers = set()

    def subscribe(self) -> asyncio.Queue:
        """
        Create a new subscription queue and register it.
        """
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """
        Remove a subscription queue.
        """
        self._subscribers.discard(queue)

    async def broadcast(self, message):
        """
        Broadcast a message to all subscribers.
        """
        # Make a copy to avoid modification during iteration.
        for queue in list(self._subscribers):
            await queue.put(message)


@asynccontextmanager
async def subscription(broadcaster: Broadcaster):
    """
    Async context manager that subscribes to a broadcaster and automatically
    unsubscribes when done.
    """
    queue = broadcaster.subscribe()
    try:
        yield queue
    finally:
        broadcaster.unsubscribe(queue)


async def queue_iterator(queue: asyncio.Queue):
    """
    Async generator to iterate over queue items.
    It will run indefinitely, so you'll need some sort of stop condition.
    """
    while item := await queue.get():
        yield item


class EventHub:
    def __init__(self):
        self.subscriptions: dict[uuid.UUID, list[asyncio.Queue]] = defaultdict(list)
        self.subscribed_at: dict[uuid.UUID, datetime] = dict()

    def subscribe(self, character_id: uuid.UUID) -> asyncio.Queue:
        """Create a new queue for this character and add it to the subscription list."""
        q = asyncio.Queue()
        if character_id not in self.subscriptions:
            self.subscribed_at[character_id] = datetime.now()
        self.subscriptions[character_id].append(q)
        return q

    def unsubscribe(self, character_id: uuid.UUID, q: asyncio.Queue):
        """Remove the given queue from this character's subscription list."""
        if character_id in self.subscriptions:
            try:
                self.subscriptions[character_id].remove(q)
            except ValueError:
                pass
            # If no more queues remain for this character, remove the key.
            if not self.subscriptions[character_id]:
                del self.subscriptions[character_id]
                del self.subscribed_at[character_id]

    async def send(self, character_id: uuid.UUID, message):
        """Send a message to all subscribers for this character."""
        if character_id in self.subscriptions:
            # iterate a copy to prevent possible mutation during iteration
            for q in self.subscriptions[character_id].copy():
                await q.put(message)

    def send_nowait(self, character_id: uuid.UUID, message):
        if character_id in self.subscriptions:
            for q in self.subscriptions[character_id].copy():
                q.put_nowait(message)

    async def broadcast(self, message):
        """Send a message to all subscribers blindly."""
        for channel_list in self.subscriptions.values():
            for channel in channel_list:
                await channel.put(message)

    def broadcast_nowait(self, message):
        for channel_list in self.subscriptions.values():
            for channel in channel_list:
                channel.put_nowait(message)

    def online(self) -> set[uuid.UUID]:
        """Return a set of all currently online characters."""
        return set(self.subscriptions.keys())

    def connected_at(self) -> dict[uuid.UUID, datetime]:
        return self.subscribed_at.copy()
