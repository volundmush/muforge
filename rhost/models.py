import fnmatch
import re
import typing
from collections import defaultdict
from enum import IntEnum


class ObjectType(IntEnum):
    ROOM = 0
    THING = 1
    EXIT = 2
    PLAYER = 3
    ZONE = 4
    GARBAGE = 5


RE_DBREF = re.compile(r"^#(?P<dbref>\d+)$")
RE_OBJID = re.compile(r"^#(?P<dbref>\d+):(?P<csecs>\d+)$")
RE_TAG = re.compile(r"^#(?P<tag>[A-Za-z]+)$")


class MushObject:
    __slots__ = (
        "dbref",
        "name",
        "type",
        "parent",
        "owner",
        "zone",
        "location",
        "csecs",
        "attributes",
        "flag_bits",
        "toggle_bits",
        "zones",
        "bitlevel",
    )

    def __init__(self, dbref: int, name: str):
        self.dbref: int = dbref
        self.name: str = name
        self.type: ObjectType = ObjectType.GARBAGE
        self.csecs: int = 0
        self.parent: int = -1
        self.owner: int = -1
        self.zone: int = -1
        self.location: int = -1
        self.attributes: dict[int, str] = dict()
        self.flag_bits: list[int] = list()
        self.toggle_bits: list[int] = list()
        self.zones: list[int] = list()
        self.bitlevel: int = 0

    @property
    def objid(self):
        return f"#{self.dbref}:{self.csecs}"

    def __repr__(self):
        return f"<{self.type.name} {self.objid} {self.name}>"


class MushAttribute:
    __slots__ = ("id", "flags", "name")

    def __init__(self, id: int, flags: int, name: str):
        self.id: int = id
        self.flags: int = flags
        self.name: str = name

    def __repr__(self):
        return f"<Attribute {self.id} - {self.name}>"


OBJECT_TARGET = typing.Union[int, str, MushObject]
ATTR_TARGET = typing.Union[str, int, MushAttribute]


class Database:
    def __init__(self):
        self.objects: dict[int, MushObject] = dict()
        self.types: dict[ObjectType, dict[int, MushObject]] = defaultdict(dict)
        self.attributes: dict[int, MushAttribute] = dict()
        self.attributes_str: dict[str, MushAttribute] = dict()
        self.tags: dict[str, MushObject] = dict()

    def setup(self):
        objid_attr = self.attributes_str.get("__OBJID_INTERNAL")
        for v in self.objects.values():
            data = v.attributes.get(objid_attr.id, None)
            if data:
                v.csecs = int(data)
            if tag := v.attributes.get(251, None):
                self.tags[tag] = v

    def _ensure_obj(self, target: OBJECT_TARGET) -> MushObject | None:
        if isinstance(target, int):
            return self.objects.get(target, None)
        elif isinstance(target, str):
            match = RE_DBREF.match(target)
            if match:
                return self.objects.get(int(match.group("dbref")), None)
            match = RE_OBJID.match(target)
            if match:
                if found := self.objects.get(int(match.group("dbref")), None):
                    csecs = int(match.group("csecs"))
                    if found.csecs == csecs:
                        return found
                return None
            match = RE_TAG.match(target)
            if match:
                return self.tags.get(match.group("tag"), None)
        elif isinstance(target, MushObject):
            return target
        return None

    def _ensure_attr(self, target: ATTR_TARGET) -> MushAttribute | None:
        if isinstance(target, int):
            return self.attributes.get(target, None)
        elif isinstance(target, str):
            return self.attributes_str.get(target, None)
        elif isinstance(target, MushAttribute):
            return target
        return None

    def contents(self, target: OBJECT_TARGET) -> list[MushObject]:
        obj = self._ensure_obj(target)
        if obj is None:
            return []
        return [v for k, v in self.objects.items() if v.location == obj.dbref]

    def children(self, target: OBJECT_TARGET) -> list[MushObject]:
        obj = self._ensure_obj(target)
        if obj is None:
            return []
        return [v for k, v in self.objects.items() if v.parent == obj.dbref]

    def parent(self, target: OBJECT_TARGET) -> MushObject | None:
        obj = self._ensure_obj(target)
        if obj is None:
            return None
        return self.objects.get(obj.parent, None)

    def location(self, target: OBJECT_TARGET) -> MushObject | None:
        obj = self._ensure_obj(target)
        if obj is None:
            return None
        return self.objects.get(obj.location, None)

    def get(
        self, target: OBJECT_TARGET, atarrget: ATTR_TARGET, inherit=True
    ) -> str | None:
        obj = self._ensure_obj(target)
        if obj is None:
            return None
        attr = self._ensure_attr(atarrget)
        if attr is None:
            return None

        current = obj
        while current is not None:
            value = current.attributes.get(attr.id, None)
            if value is not None:
                return value
            if inherit and (parent := self.parent(current)):
                current = parent
            else:
                current = None

    def lattr(
        self, target: OBJECT_TARGET, attr_mask: str, inherit=True
    ) -> dict[str, str]:
        """
        Returns a dictionary of attributes and values for the object whhere the
        attribute_name glob-matches the mask.

        For example, if an object had the attributes "CUSHION" and "CUDGEL",
        both would be returned using "CU*" as a mask.
        """

        obj = self._ensure_obj(target)
        out = dict()

        candidates: list[MushAttribute] = list()
        for k, v in self.attributes.items():
            if fnmatch.fnmatchcase(v.name.lower(), attr_mask.lower()):
                candidates.append(v)

        # after gathering candidates...
        for candidate in candidates:
            value = self.get(obj, candidate, inherit=inherit)
            if value is not None:
                out[candidate.name] = value

        return out
