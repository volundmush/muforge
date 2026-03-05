from typing import Annotated

import jwt
from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext

import muforge
from muforge.shared.fastapi import get_pg_conn, stream, transaction
from muforge.shared.models.auth import RefreshTokenModel, TokenResponse, UserLogin

crypt_context = CryptContext(
    schemes=["argon2", "sha512_crypt", "plaintext"],
    deprecated=["sha512_crypt", "plaintext"],
)

router = APIRouter()


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


async def handle_login(
    conn: Connection, request: Request, username: str, password: str
) -> TokenResponse:
    ip = request.client.host
    user_agent = request.headers.get("User-Agent", None)

    result = await authenticate_user(conn, username, password, ip, user_agent)
    return TokenResponse.from_uuid(result.id)


@router.post("/register", response_model=TokenResponse)
async def register(
    request: Request,
    data: Annotated[UserLogin, Body()],
    conn: Connection = Depends(get_pg_conn),
):

    user = await register_user(conn, data.username, data.password.get_secret_value())
    token = TokenResponse.from_uuid(user.id)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    data: Annotated[OAuth2PasswordRequestForm, Depends()],
    conn: Connection = Depends(get_pg_conn),
):
    return await handle_login(conn, request, data.username, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(ref: Annotated[RefreshTokenModel, Body()]):
    jwt_settings = muforge.SETTINGS["JWT"]
    try:
        payload = jwt.decode(
            ref.refresh_token,
            jwt_settings["secret"],
            algorithms=[jwt_settings["algorithm"]],
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )
        # Get user identifier from token. For example:
    if not payload.get("refresh", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )
    if (sub := payload.get("sub", None)) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload."
        )

    # Verify user exists. This will raise if not.
    user = await users_db.get_user(sub)

    return TokenResponse.from_uuid(sub)
