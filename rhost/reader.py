from .models import (
    ATTR_TARGET,
    OBJECT_TARGET,
    Database,
    MushAttribute,
    MushObject,
    ObjectType,
)


def _parse_attr(file) -> tuple[int, int, str]:
    """
    When this is called, file is pointed at the beginning of a line.

    If the line begins with START OF HEADER (0x01), then the format is:
        <num>:<num>:<body>
    Else it is just:
        <body>

    The body section's end is a \n that is NOT preceded by \r.
    """
    num_1: int = -1
    num_2: int = -1
    body = ""

    line = file.readline()
    if line == "":
        raise ValueError("Unexpected EOF while reading attribute")
    if line.startswith("\x01"):
        header = line[1:].rstrip("\n")
        parts = header.split(":", 2)
        if len(parts) == 3:
            num_1 = int(parts[0])
            num_2 = int(parts[1])
            body = parts[2]
        else:
            body = header
    else:
        body = line.rstrip("\n")

    while line.endswith("\r\n"):
        line = file.readline()
        if line == "":
            break
        body += line.rstrip("\n")

    return num_1, num_2, body


def parse_flatfile(
    file_path: str,
    zone: bool = False,
    atrkey: bool = True,
    parent: bool = False,
    money: bool = True,
    flags: bool = True,
) -> Database:
    with open(file_path, mode="r", newline="") as file:
        mode = "start"
        gathering = dict()
        current_obj = None
        current_attr = None
        db = Database()
        pos = None

        try:
            while True:
                match mode:
                    case "start":
                        pos = file.tell()
                        if not (line := file.readline().strip()):
                            pos = file.tell()
                            raise ValueError("Unexpected blank line")
                        if not line.startswith("+"):
                            pos = file.tell()
                            raise ValueError(f"Expected +, got {line[0]}")
                        if line.startswith("+A"):
                            mode = "attribute"
                            file.seek(pos)
                    case "attribute":
                        pos = file.tell()
                        if not (line := file.readline().strip()):
                            pos = file.tell()
                            raise ValueError("Unexpected blank line")
                        if line.startswith("+A"):
                            # this is the expecteed path
                            id = int(line[2:])
                            if not (line := file.readline().strip()):
                                pos = file.tell()
                                raise ValueError("Unexpected blank line")
                            bits, name = line.split(":", 1)
                            bits = int(bits)
                            attr = MushAttribute(id, bits, name)
                            db.attributes[id] = attr
                            db.attributes_str[name] = attr
                        elif line.startswith("!"):
                            mode = ("object", "header")
                            file.seek(pos)
                            gathering.clear()
                        else:
                            pos = file.tell()
                            raise ValueError("Unexpected end of attribute section.")
                    case ("object", "header"):
                        pos = file.tell()
                        line = file.readline().strip()
                        if line == "***END OF DUMP***":
                            db.setup()
                            return db
                        dbref = int(line[1:])
                        name = file.readline().strip()
                        obj = MushObject(dbref, name)
                        obj.location = int(file.readline().strip())
                        if zone:
                            obj.zone = int(file.readline().strip())
                        for _ in range(4):  # skip contents, exits, link, next
                            file.readline().strip()
                        if atrkey:
                            _ = file.readline().strip()
                        obj.owner = int(file.readline().strip())
                        if parent:
                            obj.parent = int(file.readline().strip())
                        if money:
                            _ = file.readline().strip()
                        obj.flag_bits.append(int(file.readline().strip()))
                        if flags:
                            for _ in range(3):
                                obj.flag_bits.append(int(file.readline().strip()))
                            for _ in range(8):
                                obj.toggle_bits.append(int(file.readline().strip()))
                            while True:
                                zone = file.readline().strip()
                                if zone == "-1":
                                    break
                                obj.zones.append(int(zone))

                        type_flags = obj.flag_bits[0] & 0x7
                        if type_flags == 0:
                            obj.type = ObjectType.ROOM
                        elif type_flags == 1:
                            obj.type = ObjectType.THING
                        elif type_flags == 2:
                            obj.type = ObjectType.EXIT
                        elif type_flags == 3:
                            obj.type = ObjectType.PLAYER
                        elif type_flags == 4:
                            obj.type = ObjectType.ZONE
                        elif type_flags == 5:
                            obj.type = ObjectType.GARBAGE

                        db.objects[obj.dbref] = obj
                        db.types[obj.type][obj.dbref] = obj
                        current_obj = obj
                        if obj.dbref == 1:
                            obj.bitlevel = 7
                        elif flags & 0x00200000:
                            obj.bitlevel = 6
                        elif flags & 0x00000010:
                            obj.bitlevel = 5

                        mode = ("object", "attributes")
                    case ("object", "attributes"):
                        pos = file.tell()
                        if not (line := file.readline().rstrip("\n")):
                            pos = file.tell()
                            raise ValueError("Unexpected blank line")
                        if line.startswith(">"):
                            attr_id = int(line[1:].strip())
                            # attr = db.attributes.get(attr_id)
                            num_1, num_2, body = _parse_attr(file)
                            current_obj.attributes[attr_id] = body
                        elif line.startswith("<"):
                            # end of attributes section
                            mode = ("object", "header")

        except ValueError as e:
            err_pos = pos if pos is not None else file.tell()
            try:
                current_pos = file.tell()
                context_start = max(err_pos - 200, 0)
                file.seek(context_start)
                context = file.read(400)
                file.seek(current_pos)
            except Exception:
                context_start = err_pos
                context = ""
            raise ValueError(
                f"{e} in Mode {mode}: {err_pos}\n"
                f"Context (pos {context_start}-{context_start + len(context)}):\n{context}"
            )

        db.setup()
        return db
