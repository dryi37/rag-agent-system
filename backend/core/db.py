import os
from typing import Optional, AsyncGenerator

from psycopg_pool import AsyncConnectionPool
import psycopg

# Database pool
_db_pool: Optional[AsyncConnectionPool] = None

async def init_db_pool() -> None:
    global _db_pool
    if _db_pool is None:
        db_url = os.getenv("POSTGRES_URL")
        if not db_url:
            raise RuntimeError("POSTGRES_URL not configured")
            
        _db_pool = AsyncConnectionPool(db_url, min_size=1, max_size=10, open=False)
        await _db_pool.open()


async def close_db_pool() -> None:
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()


async def get_db() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    if _db_pool is None:
        raise RuntimeError("DB pool not initialised.")
    async with _db_pool.connection() as conn:
        yield conn

def get_db_pool() -> AsyncConnectionPool:
    if _db_pool is None:
        raise RuntimeError("DB pool not initialised.")
    return _db_pool