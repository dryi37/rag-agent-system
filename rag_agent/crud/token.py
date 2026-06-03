import hashlib
from typing import Optional

from psycopg.rows import dict_row
from jose import jwt

from datetime import datetime, timezone
import psycopg

# Refresh token
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _get_token_expiry(token: str) -> datetime:
    """Lấy exp từ JWT payload, không verify signature."""
    payload = jwt.decode(token, options={"verify_signature": False})
    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

async def save_refresh_token(db: psycopg.AsyncConnection, user_id: int, token: str) -> None:
    expires_at = _get_token_expiry(token)
    async with db.cursor() as cur:
        await cur.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, _hash_token(token), expires_at),
        )


async def get_refresh_token(db: psycopg.AsyncConnection, token: str) -> Optional[dict]:
    async with db.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, user_id FROM refresh_tokens
            WHERE token_hash = %s AND revoked = FALSE AND expires_at > NOW()
            """,
            (_hash_token(token),),
        )
        return await cur.fetchone()


async def revoke_refresh_token(db: psycopg.AsyncConnection, token: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = %s",
            (_hash_token(token),),
        )
