import logging
from typing import Optional, AsyncGenerator

from psycopg_pool import AsyncConnectionPool
import psycopg


logger = logging.getLogger(__name__)

# Database pool
_db_pool: Optional[AsyncConnectionPool] = None


async def init_db_pool(dsn: str) -> None:
    global _db_pool
    _db_pool = AsyncConnectionPool(dsn, open=False)
    await _db_pool.open()
    logger.info("DB pool initialised.")


async def close_db_pool() -> None:
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        logger.info("DB pool closed.")


async def get_db() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    if _db_pool is None:
        raise RuntimeError("DB pool not initialised.")
    async with _db_pool.connection() as conn:
        yield conn