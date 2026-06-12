from typing import Optional
import psycopg
from psycopg.rows import dict_row


async def create_thread(
    db: psycopg.AsyncConnection,
    thread_id: str,
    user_id: Optional[int] = None,
) -> dict:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO threads (id, user_id)
            VALUES (%s, %s)
            RETURNING id, user_id, created_at
            """,
            (thread_id, user_id),
        )
        return await cur.fetchone()


async def save_message(
    db: psycopg.AsyncConnection,
    thread_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> dict:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO messages (thread_id, role, content, sources)
            VALUES (%s, %s, %s, %s)
            RETURNING id, thread_id, role, content, sources, created_at
            """,
            (thread_id, role, content, psycopg.types.json.Jsonb(sources or [])),
        )
        return await cur.fetchone()


async def get_thread_messages(
    db: psycopg.AsyncConnection,
    thread_id: str,
) -> list[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, role, content, sources, created_at
            FROM messages
            WHERE thread_id = %s
            ORDER BY created_at ASC
            """,
            (thread_id,),
        )
        return await cur.fetchall()
    
async def get_user_threads(
    db: psycopg.AsyncConnection,
    user_id: int,
) -> list[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT t.id, t.created_at,
                   (SELECT content FROM messages
                    WHERE thread_id = t.id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) AS preview
            FROM threads t
            WHERE t.user_id = %s
            ORDER BY t.created_at DESC
            LIMIT 50
            """,
            (user_id,),
        )
        return await cur.fetchall()


async def get_last_assistant_message(
    db: psycopg.AsyncConnection,
    thread_id: str,
) -> Optional[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, role, content, sources, created_at
            FROM messages
            WHERE thread_id = %s AND role = 'assistant'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (thread_id,),
        )
        return await cur.fetchone()