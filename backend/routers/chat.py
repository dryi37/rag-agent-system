import asyncio
import json
import uuid
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import get_current_user
from backend.agent.runner import run_agent
from backend.schemas import MessageRequest, ThreadResponse
from backend.core.db import get_db
from backend.crud.thread import save_message, create_thread


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
