from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException, status

from muforge.shared.models.users import UserModel
from muforge.shared.utils import crypt_context

from .base import transaction


@transaction
async def register_user(conn: Connection, username: str, password: str) -> UserModel:
    admin_level = 0

    try:
        hashed = crypt_context.hash(password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error hashing password."
        )

    # if there are no users, make this user an admin.
    if not (await conn.fetchrow("SELECT id FROM users")):
        admin_level = 10

    try:
        # Insert the new user.
        user_row = await conn.fetchrow(
            """
            INSERT INTO users (username, admin_level)
            VALUES ($1, $2)
            RETURNING *
            """,
            username,
            admin_level,
        )
    except UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists.",
        )
    user = UserModel(**user_row)

    # Insert the password record.
    password_row = await conn.fetchrow(
        """
        INSERT INTO passwords (user_id, password_hash)
        VALUES ($1, $2)
        RETURNING id
        """,
        user.id,
        hashed,
    )
    password_id = password_row["id"]

    # Update the user to set the current password.
    await conn.execute(
        "UPDATE users SET current_password_id=$1 WHERE id=$2",
        password_id,
        user.id,
    )
    return user


@transaction
async def authenticate_user(
    conn: Connection, email: str, password: str, ip: str, user_agent: str | None
) -> UserModel:
    # Retrieve the latest password row for this user.
    retrieved_user = await conn.fetchrow(
        """
        SELECT *
        FROM user_passwords
        WHERE email = $1 LIMIT 1
        """,
        email,
    )
    if not (
        retrieved_user
        and retrieved_user["password_hash"]
        and crypt_context.verify(password, retrieved_user["password_hash"])
    ):
        await conn.execute(
            """
            INSERT INTO loginrecords (user_id, ip_address, success, user_agent)
            VALUES ($1, $2, $3, $4)
            """,
            retrieved_user["id"],
            ip,
            False,
            user_agent,
        )
        raise HTTPException(status_code=400, detail="Invalid credentials.")

    if crypt_context.needs_update(retrieved_user["password_hash"]):
        try:
            hashed = crypt_context.hash(password)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error hashing password.",
            )
        password_row = await conn.fetchrow(
            """
            INSERT INTO passwords (user_id, password_hash)
            VALUES ($1, $2)
            RETURNING id
            """,
            retrieved_user["id"],
            hashed,
        )
        password_id = password_row["id"]

        # Update the user to set the current password.
        await conn.execute(
            "UPDATE users SET current_password_id=$1 WHERE id=$2",
            password_id,
            retrieved_user["id"],
        )

    # Record successful login.
    await conn.execute(
        """
        INSERT INTO loginrecords (user_id, ip_address, success, user_agent)
        VALUES ($1, $2, $3, $4)
        """,
        retrieved_user["id"],
        ip,
        True,
        user_agent,
    )

    return UserModel(**retrieved_user)
