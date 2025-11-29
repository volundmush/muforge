
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class NodeSchema(BaseModel):
    id: str
    name: str
    desc: str = ""
    kind: str = ""
    exits: Dict[str, str] = Field(default_factory=dict)
    controls: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class RoomSchema(BaseModel):
    id: str
    name: str
    desc: str = ""
    kind: str = "room"
    controls: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)