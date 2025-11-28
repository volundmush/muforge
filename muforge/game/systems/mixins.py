import weakref

class HasLocation:

    def __init__(self) -> None:
        self.location: "None | weakref.ReferenceType[BaseLocation | Object | Structure | Character]" = None
        self.location_data: dict = dict()

    def get_location(self) -> "None | BaseLocation | Object | Structure | Character":
        if self.location and (loc := self.location()) is not None:
            return loc
        return None

class HasInventory:

    def __init__(self) -> None:
        self.inventory: list[weakref.ReferenceType["Object"]] = list()

    def get_inventory(self) -> list["Object"]:
        return [x for obj_ref in self.inventory if (x := obj_ref()) is not None]

class HasEquipment:

    def __init__(self) -> None:
        self.equipment: dict[str, weakref.ReferenceType["Object"]] = dict()

    def get_equipment(self) -> dict[str, "Object"]:
        return {slot: x for slot, obj_ref in self.equipment.items() if (x := obj_ref()) is not None}

class HasKeywords:

    def __init__(self) -> None:
        self.keywords: list[str] = list()
    
    def get_keywords(self) -> list[str]:
        return list(self.keywords)