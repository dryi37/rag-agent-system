from typing import Optional

import psycopg
from psycopg.rows import dict_row

from rag_agent.core.security import verify_password

async def get_user_by_id(db: psycopg.AsyncConnection, user_id: int) -> Optional[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        return await cur.fetchone()


async def create_user(db: psycopg.AsyncConnection, username: str, email: str, hashed_password: str) -> dict:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO users (username, email, hashed_password)
            VALUES (%s, %s, %s)
            RETURNING id, username, email, created_at
            """,
            (username, email, hashed_password),
        )
        return await cur.fetchone()


async def authenticate_user(db: psycopg.AsyncConnection, username: str, password: str) -> Optional[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, username, email, hashed_password FROM users WHERE username = %s",
            (username,),
        )
        user = await cur.fetchone()
    if user is None or not verify_password(password, user["hashed_password"]):
        return None
    return user
