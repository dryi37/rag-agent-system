from typing import Optional

from fastapi import Depends
import psycopg

from backend.core.security import oauth2_scheme, verify_token
from backend.core.db import get_db
from backend.crud.user import get_user_by_id

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: psycopg.AsyncConnection = Depends(get_db),
) -> Optional[dict]:
    if token is None:
        return None
    payload = verify_token(token, token_type="access")
    if payload is None:
        return None
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        return None
    return await get_user_by_id(db, int(user_id_str))
