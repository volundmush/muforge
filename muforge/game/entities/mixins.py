import weakref

class HasLocation:

    def __init__(self) -> None:
        self.location: "None | BaseLocation | Object | Structure | Character" = None
        self.location_data: dict = dict()
    
    async def move_to(self, new_location: "BaseLocation | Object | Structure | Character") -> None:
        old_location = None
        if self.location:
            if self.location == new_location:
                return
            old_location = self.location
            self.location.contents.remove(self)
            for character in self.location.contents:
                if character is not self:
                    await character.send_line(f"{self.get_display_name(character)} heads to {new_location}.")
        self.location = new_location
        new_location.contents.append(self)

        for character in new_location.contents:
            if character is not self:
                await character.send_line(f"{self.get_display_name(character)} has arrived from {old_location if old_location else 'somewhere unknown'}.")

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