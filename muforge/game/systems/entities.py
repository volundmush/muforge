import uuid

class BaseEntity:
    entity_type: str = None
    entity_family: str = None
    
    def __init__(self, id: uuid.UUID, name: str):
        self.id = id
        self.name = name

    def get_display_name(self, viewer: "Character") -> str:
        return self.name
    
    def get_search_keywords(self) -> list[str]:
        return self.name.lower().split()
    
    def render_description(self, viewer: "Character") -> str:
        return f"{self.get_display_name(viewer)} (an entity of type {self.entity_type})"
    
    def render_for_location_view(self, viewer: "Character") -> str:
        return self.get_display_name(viewer)
    
    def render_for_inventory_view(self, viewer: "Character") -> str:
        return self.get_display_name(viewer)
    
    def _save_base(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "entity_family": self.entity_family,
            "entity_class": f"{self.__class__.__module__}.{self.__class__.__name__}",
        }
    
    def save_data(self) -> dict:
        return dict()

    def export_save(self) -> dict:
        base = self._save_base()
        base["data"] = self.save_data()
        return base
