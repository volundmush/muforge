
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class Location(BaseModel):
    id: str
    name: str
    desc: str = ""
    tags: List[str] = Field(default_factory=list)
    exits: Dict[str, str] = Field(default_factory=dict)
    contents: List[Any] = Field(exclude=True, default_factory=list)

    def get_neighbors(self, target: "BaseEntity") -> list["BaseEntity"]:
        return [x for x in self.contents if x is not target]

    def __str__(self) -> str:
        return self.name