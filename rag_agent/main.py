import os
import logging
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langfuse import propagate_attributes

from rag_agent.graph import get_graph, close_checkpointer
from rag_agent.inference_clients import close_clients
from rag_agent.agent import init_mcp_client, close_mcp_client
from rag_agent.redis_modules import get_redis
from rag_agent.redis_modules.cache import SemanticCache
from rag_agent.redis_modules.streams import EventPublisher, EventSubscriber
from rag_agent.langfuse.client import langfuse
from rag_agent.langfuse.handler import get_langfuse_handler

load_dotenv()

logger = logging.getLogger(__name__)

# 

class ThreadResponse(BaseModel):
    thread_id: str


class MessageRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    max_iterations: int = 3
    skip_cache: bool = False


class ThreadResult(BaseModel):
    answer: str
    sources: list[dict]
    iterations: int
    cache_hit: bool = False


# Lifespan 

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = await get_graph()
    redis = await get_redis()
    app.state.redis = redis
    app.state.embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    app.state.semantic_cache = SemanticCache(redis, app.state.embeddings)
    app.state.publisher = EventPublisher(redis)
    app.state.subscriber = EventSubscriber(redis)
    await init_mcp_client()
    print("[INFO] Redis connected")
    print("[INFO] Graph initialized")
    print("[INFO] MCP client initialized")
    yield
    await redis.aclose()
    await close_clients()
    await close_mcp_client()
    await close_checkpointer()
    langfuse.shutdown()


app = FastAPI(
    title="RAG Agent",
    version="1.0.0",
    lifespan=lifespan,
)


# Background task

async def _run_agent(
    thread_id: str,
    request: MessageRequest,
    graph,
    semantic_cache: SemanticCache,
    publisher: EventPublisher,
):
    if not request.skip_cache:
        cached = await semantic_cache.get(request.query)
        if cached:
            await publisher.done(
                thread_id,
                answer=cached["answer"],
                sources=cached.get("sources", []),
                iterations=0,
                from_cache=True,
            )
            return
        
    langfuse_handler = get_langfuse_handler()

    with langfuse.start_as_current_observation(as_type="span", name="rag_agent") as span:
        with propagate_attributes(
            session_id=thread_id,
            user_id=request.user_id or "anonymous",
            tags=["rag_agent"],
            input={"query": request.query},
        ):
            initial_state = {
                "query": request.query,
                "thread_id": thread_id,
                "generation": "",
                "max_iterations": request.max_iterations,
            }
            config = {
                "configurable": {
                    "thread_id": thread_id, 
                    "publisher": publisher
                },
                "callbacks": [langfuse_handler],

            }

            try:
                final_state = await graph.ainvoke(initial_state, config=config)
            except Exception as e:
                logger.exception(f"[{thread_id}] _run_agent failed: {e}")
                await publisher.error(thread_id, str(e))
                return

            sources = [
                {"source": doc.get("source", ""), "type": doc.get("type", "")}
                for doc in final_state.get("retrieved_docs", [])
            ]
        span.update(
            output={
                "answer": final_state.get("generation"),
                "sources": sources
            }
        )

    await semantic_cache.set(
        query=request.query,
        answer=final_state["generation"],
        metadata={"sources": sources, "iterations": final_state.get("iterations", 1)},
    )

    await publisher.done(
        thread_id,
        answer=final_state["generation"],
        sources=sources,
        iterations=final_state.get("iterations", 0),
    )

# Endpoints 

@app.get("/health")
async def health():
    try:
        await app.state.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": "ok" if redis_ok else "error"}


@app.post("/threads", response_model=ThreadResponse, status_code=201)
async def create_thread():
    thread_id = str(uuid.uuid4())
    # nên viết module cho clean hơn
    await app.state.redis.setex(
        f"thread:{thread_id}",
        7200,
        json.dumps({"created_at": datetime.now(timezone.utc).isoformat()})
    )
    return ThreadResponse(thread_id=thread_id)


@app.post("/threads/{thread_id}/messages", status_code=202)
async def send_message(thread_id: str, request: MessageRequest):
    if not await app.state.redis.exists(f"thread:{thread_id}"):
        raise HTTPException(status_code=404, detail="Thread not found")
    asyncio.create_task(_run_agent(
        thread_id=thread_id,
        request=request,
        graph=app.state.graph,
        semantic_cache=app.state.semantic_cache,
        publisher=app.state.publisher,
    ))
    return ThreadResponse(thread_id=thread_id)


@app.get("/threads/{thread_id}/events")
async def get_thread_events(
    thread_id: str,
    last_event_id: str = Query(default="0", description="last event id — use when reconnect"),
):
    subscriber: EventSubscriber = app.state.subscriber

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in subscriber.subscribe(thread_id, last_event_id=last_event_id):
            yield f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/threads/{thread_id}", response_model=ThreadResult)
async def get_thread(thread_id: str):
    result = await app.state.subscriber.get_result(thread_id)
    if not result:
        raise HTTPException(status_code=404, detail="Thread not found or not done yet")
    return ThreadResult(**result)


@app.delete("/cache", status_code=204)
async def clear_cache():
    await app.state.semantic_cache.clear_all()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rag_agent.main:app", host="0.0.0.0", port=8000, reload=False)
