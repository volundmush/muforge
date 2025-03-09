from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from pydantic import BaseModel

import orjson
import re
import typing
import mudforge
import jwt
import uuid
import pydantic

from tortoise.expressions import RawSQL
from tortoise.transactions import in_transaction

from asyncpg import exceptions

from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from .utils import (
    crypt_context,
    oauth2_scheme,
    get_real_ip,
    get_current_user,
    get_acting_character,
)
from .models import (
    BoardModel,
    PostModel,
    FactionModel,
    ActiveAs,
    UserModel,
    CharacterModel,
)

router = APIRouter()

RE_BOARD_ID = re.compile(r"^(?P<abbr>[a-zA-Z]+)?(?P<order>\d+)$")


class BoardCreate(BaseModel):
    name: str
    board_key: str

    class Config:
        from_attributes = True


@router.post("/", response_model=BoardModel)
async def create_board(
    board: Annotated[BoardCreate, Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    if not (matched := RE_BOARD_ID.match(board.board_key)):
        raise HTTPException(status_code=400, detail="Invalid board ID format.")
    order = int(matched.group("order"))
    faction = None
    board_data = None
    faction_data = None
    async with mudforge.PGPOOL.acquire() as conn:
        if abbr := matched.group("abbr"):
            if not (
                faction_data := await conn.fetchrow(
                    "SELECT id FROM factions WHERE abbreviation = $1", abbr
                )
            ):
                raise HTTPException(
                    status_code=404, detail=f"Faction {board.board_key} not found."
                )
        if faction_data:
            faction = FactionModel(**faction_data)
            if not await faction.access(acting, "bbadmin"):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to create boards in that faction.",
                )
        else:
            if acting.admin_level < 4:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to create public boards.",
                )
        fac_id = faction.id if faction else None
        try:
            board_row = await conn.fetchrow(
                "INSERT INTO boards (faction_id, board_order, name) VALUES ($1, $2, $3) RETURNING id",
                fac_id,
                order,
                board.name,
            )
        except exceptions.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail=f"Board with order {order} already exists in faction {fac_id}.",
            )
        board_data = await conn.fetchrow(
            "SELECT * FROM board_view WHERE id = $1", board_row["id"]
        )
    return BoardModel(**board_data)


@router.get("/", response_model=typing.List[BoardModel])
async def list_boards(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)
    boards = []
    async with mudforge.PGPOOL.acquire() as conn:
        for board_data in await conn.fetch("SELECT * FROM board_view"):
            board = BoardModel(**board_data)
            if await board.access(acting, "read"):
                boards.append(board)
    return boards


@router.get("/{board_key}", response_model=BoardModel)
async def get_board(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        board_data = await conn.fetchrow(
            "SELECT * FROM board_view WHERE board_key = $1", board_key
        )
        if board_data is None:
            raise HTTPException(status_code=404, detail="Board not found.")
        board = BoardModel(**board_data)
        if not await board.access(acting, "read"):
            raise HTTPException(
                status_code=403, detail="You do not have permission to read this board."
            )
        return board


@router.get("/{board_key}/posts", response_model=list[PostModel])
async def list_posts(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        board_data = await conn.fetchrow(
            "SELECT * FROM board_view WHERE board_key = $1", board_key
        )
        if board_data is None:
            raise HTTPException(status_code=404, detail="Board not found.")
        board = BoardModel(**board_data)
        admin = await board.access(acting, "admin")
        if not admin:
            if not await board.access(acting, "read"):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to read this board.",
                )
        posts_data = await conn.fetch(
            "SELECT * FROM board_post_view WHERE board_id = $1", board.id
        )
        posts = [PostModel(**post) for post in posts_data]
        if board.anonymous_name:
            if not admin:
                for post in posts:
                    post.spoofed_name = board.anonymous_name
                    post.character_id = None
                    post.character_name = None
                else:
                    post.spoofed_name = f"{board.anonymous_name} ({post.spoofed_name})"
        return posts


@router.get("/{board_key}/posts/{post_key}", response_model=PostModel)
async def get_post(
    board_key: str,
    post_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        board_data = await conn.fetchrow(
            "SELECT * FROM board_view WHERE board_key = $1", board_key
        )
        if board_data is None:
            raise HTTPException(status_code=404, detail="Board not found.")
        board = BoardModel(**board_data)
        admin = await board.access(acting, "admin")
        if not admin:
            if not await board.access(acting, "read"):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to read this board.",
                )
        post_data = await conn.fetchrow(
            "SELECT * FROM board_post_view WHERE board_id = $1 AND post_key = $2",
            board.id,
            post_key,
        )
        if post_data is None:
            raise HTTPException(status_code=404, detail="Post not found.")
        post = PostModel(**post_data)
        if board.anonymous_name:
            if not admin:
                post.spoofed_name = board.anonymous_name
                post.character_id = None
                post.character_name = None
            else:
                post.spoofed_name = f"{board.anonymous_name} ({post.spoofed_name})"
        return post


class PostCreate(BaseModel):
    title: str
    body: str


@router.post("/{board_key}/posts", response_model=PostModel)
async def create_post(
    board_key: str,
    post: PostCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            board_data = await conn.fetchrow(
                "SELECT * FROM board_view WHERE board_key = $1", board_key
            )
            if board_data is None:
                raise HTTPException(status_code=404, detail="Board not found.")
            board = BoardModel(**board_data)
            if not await board.access(acting, "post"):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to write to this board.",
                )
            max_order = await conn.fetchval(
                "SELECT MAX(post_order) FROM board_posts WHERE board_id = $1", board.id
            )
            post_data = await conn.fetchrow(
                "INSERT INTO board_posts (board_id, title, body, post_order, sub_order, spoof_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                board.id,
                post.title,
                post.body,
                max_order + 1,
                0,
                acting.spoofing_id,
            )
            read = await conn.fetchrow(
                "INSERT INTO board_posts_read (post_id, user_id) VALUES ($1, $2) RETURNING id",
                post_data["id"],
                acting.user.id,
            )
            post_data = await conn.fetchrow(
                "SELECT * FROM board_post_view WHERE id = $1", post_data["id"]
            )
            return PostModel(**post_data)


class ReplyCreate(BaseModel):
    body: str

    class Config:
        from_attributes = True


@router.post("/{board_key}/posts/{post_key}", response_model=PostModel)
async def create_reply_post(
    board_key: str,
    post_key: str,
    reply: ReplyCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    async with mudforge.PGPOOL.acquire() as conn:
        async with conn.transaction():
            board_data = await conn.fetchrow(
                "SELECT * FROM board_view WHERE board_key = $1", board_key
            )
            if board_data is None:
                raise HTTPException(status_code=404, detail="Board not found.")
            board = BoardModel(**board_data)
            if not await board.access(acting, "post"):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to write to this board.",
                )
            post_data = await conn.fetchrow(
                "SELECT * FROM board_post_view WHERE board_id = $1 AND post_key = $2",
                board.id,
                post_key,
            )
            if post_data is None:
                raise HTTPException(status_code=404, detail="Post not found.")
            post = PostModel(**post_data)
            sub_order = await conn.fetchval(
                "SELECT MAX(sub_order) FROM board_posts WHERE board_id = $1 AND post_order = $2",
                board.id,
                post.order,
            )
            post_data = await conn.fetchrow(
                "INSERT INTO board_posts (board_id, title, body, post_order, sub_order, spoof_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                board.id,
                f"RE: {post.title}",
                reply.body,
                post.order,
                sub_order + 1,
                acting.spoofing_id,
            )
            read = await conn.fetchrow(
                "INSERT INTO board_posts_read (post_id, user_id) VALUES ($1, $2) RETURNING id",
                post_data["id"],
                acting.user.id,
            )
            post_data = await conn.fetchrow(
                "SELECT * FROM board_post_view WHERE id = $1", post_data["id"]
            )
            return PostModel(**post_data)
