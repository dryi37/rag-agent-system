import asyncio
import json
import uuid
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from dependencies import get_current_user
from agent.runner import run_agent
from schemas import MessageRequest, ThreadResponse
from core.db import get_db
from crud.thread import save_message, create_thread, get_thread_messages, get_user_threads


router = APIRouter(prefix="/threads", tags=["chat"])


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_new_thread(
    current_user: Optional[dict] = Depends(get_current_user),
    db: psycopg.AsyncConnection = Depends(get_db),
):
    thread_id = str(uuid.uuid4())
    user_id = current_user["id"] if current_user else None
    await create_thread(db, thread_id=thread_id, user_id=user_id)
    return ThreadResponse(thread_id=thread_id)


@router.post("/{thread_id}/messages")
async def send_message(
    thread_id: str,
    request: MessageRequest,
    req: Request,
    current_user: Optional[dict] = Depends(get_current_user),
    db: psycopg.AsyncConnection = Depends(get_db),
):
    await save_message(db, thread_id=thread_id, role="user", content=request.query)

    async def stream_generator():
        async for event in run_agent(
            thread_id=thread_id,
            query=request.query,
            user_id=str(current_user["id"]) if current_user else "anonymous",
            graph=req.app.state.graph,
            semantic_cache=req.app.state.semantic_cache,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream",
                           headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    current_user: Optional[dict] = Depends(get_current_user),
    db: psycopg.AsyncConnection = Depends(get_db),
):
    if not current_user:
        return []
    threads = await get_user_threads(db, user_id=current_user["id"])
    return [ThreadResponse(thread_id=t["id"]) for t in threads]


@router.get("/{thread_id}/messages")
async def get_messages(
    thread_id: str,
    db: psycopg.AsyncConnection = Depends(get_db),
):
    return await get_thread_messages(db, thread_id)
