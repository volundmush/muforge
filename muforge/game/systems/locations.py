
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class LocationSchema(BaseModel):
    id: str
    name: str
    desc: str = ""
    kind: str = ""
    meta: Dict[str, Any] = Field(default_factory=dict)
    controls: List[str] = Field(default_factory=list)
    contents: List["BaseEntity"] = Field(exclude=True, default_factory=list)

    def get_neighbors(self, target: "BaseEntity") -> list["BaseEntity"]:
        return [x for x in self.contents if x is not target]


class NodeSchema(BaseModel):
    exits: Dict[str, str] = Field(default_factory=dict)


class RoomSchema(BaseModel):
    pass