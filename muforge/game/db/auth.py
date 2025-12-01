from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status

from datetime import datetime, timezone

import muforge
from muforge.shared.utils import crypt_context, fresh_uuid4

from muforge.shared.models.users import UserModel

async def register_user(
    email: str, hashed_password: str
) -> UserModel:
    admin_level = 0

    # if there are no users, make this user an admin.
    if not muforge.USERS:
        admin_level = 10
    
    for k, v in muforge.USERS.items():
        if v.email.lower() == email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists.",
            )
    id = fresh_uuid4(muforge.USERS.keys())
    data = {
        "id": id,
        "email": email,
        "display_name": email.split("@")[0],
        "password": hashed_password,
        "admin_level": admin_level,
        "email_confirmed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None
    }

    user = UserModel(**data)
    muforge.USERS[id] = user

    return user


async def authenticate_user(
    email: str, password: str, ip: str, user_agent: str | None
) -> UserModel:
    user = None
    for k, v in muforge.USERS.items():
        if v.email.lower() == email.lower():
            user = v
            break
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials.")
    
    if not crypt_context.verify(password, user.password.get_secret_value()):
        raise HTTPException(status_code=400, detail="Invalid credentials.")

    return user
