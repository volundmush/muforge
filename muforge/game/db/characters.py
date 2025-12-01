import typing
import uuid

from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status

import muforge
from muforge.shared.models.users import UserModel
from muforge.shared.models.characters import CharacterModel, ActiveAs
from muforge.shared.utils import fresh_uuid4

async def find_character_name(name: str) -> CharacterModel:
    for v in muforge.ENTITY_TYPE_INDEX.get("player", list()):
        if v.name.lower() == name.lower():
            return v.to_model()
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Character not found"
    )


async def find_character_id(
    character_id: uuid.UUID
) -> CharacterModel:
    for v in muforge.ENTITY_TYPE_INDEX.get("player", list()):
        if v.id == character_id:
            return v.to_model()
    raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Character not found"
        )



async def list_characters(

) -> typing.AsyncGenerator[CharacterModel, None]:
    query = "SELECT * FROM character_view"
    # Use a cursor to stream results rather than loading everything into memory at once.
    for t in muforge.ENTITY_TYPE_INDEX.get("player", list()):
        yield t.to_model()



async def list_characters_user(
    user: UserModel
) -> typing.AsyncGenerator[CharacterModel, None]:
    for t in muforge.ENTITY_TYPE_INDEX.get("player", list()):
        if t.user_id == user.id and t.deleted_at is None:
            yield t.to_model()


async def create_character(
    user: UserModel, name: str
) -> CharacterModel:
    
    character_class = muforge.ENTITY_CLASSES["player"]
    id = fresh_uuid4(muforge.ENTITIES.keys())

    for v in muforge.ENTITY_TYPE_INDEX.get("player", list()):
        if v.name.lower() == name.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Character name already in use"
            )
    
    character = character_class(id=id, name=name, user_id=user.id)
    user = muforge.USERS.get(user.id)
    user.characters[id] = character
    
    character.register_entity()
    return character.to_model()

async def list_online(conn: Connection) -> list[ActiveAs]:
    return [
        ActiveAs(
            character=v.pc.to_model(), user=muforge.USERS[v.user_id]
        )
        for k, v in muforge.SESSIONS.items()
    ]