import typing
import uuid

from fastapi import HTTPException, status

import muforge
from muforge.shared.models.users import UserModel

async def get_user(user_id: uuid.UUID) -> UserModel:
    if not (user := muforge.USERS.get(user_id, None)):
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
    return user

    
async def find_user(email: str) -> UserModel:
    for k, v in muforge.USERS.items():
        if v.email.lower() == email.lower():
            return v
    raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )


async def list_users() -> typing.AsyncGenerator[UserModel, None]:
    for k, v in muforge.USERS.items():
        yield v
