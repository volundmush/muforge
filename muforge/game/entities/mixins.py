import weakref

class HasLocation:

    def __init__(self) -> None:
        self.location: "None | BaseLocation | Object | Structure | Character" = None
        self.location_data: dict = dict()
    
    async def move_to(self, new_location: "BaseLocation | Object | Structure | Character") -> None:
        if self.location:
            if self.location == new_location:
                return
            self.location.contents.remove(self)
        self.location = new_location
        new_location.contents.append(self)

        for character in new_location.contents:
            if character is not self:
                await character.send_line(f"{self.get_display_name(character)} has arrived.")

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