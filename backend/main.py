import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.agent.graph import get_graph, close_checkpointer
from backend.agent.inference_clients import close_clients
from backend.agent.agent import init_mcp_client, close_mcp_client
from backend.redis_modules import get_redis
from backend.redis_modules.cache import SemanticCache
from backend.langfuse.client import langfuse
from backend.core.db import init_db_pool, close_db_pool
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router

load_dotenv()

logger = logging.getLogger(__name__)


# Lifespan 

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    app.state.graph = await get_graph()
    redis = await get_redis()
    app.state.redis = redis
    app.state.embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    app.state.semantic_cache = SemanticCache(redis, app.state.embeddings)
    await init_mcp_client()
    print("[INFO] Redis connected")
    print("[INFO] Graph initialized")
    print("[INFO] MCP client initialized")
    yield
    await close_db_pool()
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

app.include_router(auth_router)
app.include_router(chat_router)

# Endpoints 

@app.get("/health")
async def health():
    try:
        await app.state.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": "ok" if redis_ok else "error"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
