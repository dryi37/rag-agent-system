from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import psycopg

from backend.core.db import get_db
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_token,
)
from backend.crud.user import get_user_by_username, create_user
from backend.core.security import verify_password
from backend.crud.token import save_refresh_token, get_refresh_token, revoke_refresh_token
from backend.schemas import TokenResponse, UserRegister, RefreshRequest
from backend.core.security import get_token_expiry
from backend.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: psycopg.AsyncConnection = Depends(get_db)):
    user = await create_user(
        db,
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
    )
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


@router.post("/login", response_model=TokenResponse)
async def login(form_data=Depends(OAuth2PasswordRequestForm), db=Depends(get_db)):
    user = await get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    access_token = create_access_token({"sub": str(user["id"])})
    refresh_token = create_refresh_token({"sub": str(user["id"])})
    expires_at = get_token_expiry(refresh_token)
    await save_refresh_token(db, user["id"], refresh_token, expires_at)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: psycopg.AsyncConnection = Depends(get_db),
):
    payload = verify_token(body.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored = await get_refresh_token(db, body.refresh_token)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    user_id = int(payload["sub"])

    # Rotate — revoke cũ, cấp mới
    await revoke_refresh_token(db, body.refresh_token)
    new_access = create_access_token({"sub": str(user_id)})
    new_refresh = create_refresh_token({"sub": str(user_id)})
    expires_at = get_token_expiry(new_refresh)
    await save_refresh_token(db, user_id, new_refresh, expires_at)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    db: psycopg.AsyncConnection = Depends(get_db),
):
    await revoke_refresh_token(db, body.refresh_token)
