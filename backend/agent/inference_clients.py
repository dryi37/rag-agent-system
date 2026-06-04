import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

RERANKER_URL   = os.getenv("RERANKER_SERVICE_URL", "http://localhost:8002")
RERANK_TIMEOUT = float(os.getenv("RERANK_TIMEOUT", "15.0"))
THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.3"))

_reranker_client: Optional[httpx.AsyncClient] = None

def get_reranker_client() -> httpx.AsyncClient:
    global _reranker_client
    if _reranker_client is None or _reranker_client.is_closed:
        _reranker_client = httpx.AsyncClient(
            base_url=RERANKER_URL,
            timeout=RERANK_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
    return _reranker_client

async def close_clients():
    global _reranker_client
    if _reranker_client and not _reranker_client.is_closed:
        await _reranker_client.aclose()

async def rerank_documents(
    query: str,
    documents: list[dict],
    top_n: int = 5,
    content_key: str = "content",
) -> list[dict]:
    if not documents:
        return []

    client = get_reranker_client()
    try:
        response = await client.post(
            "/rerank",
            json={
                "query": query,
                "documents": [doc.get(content_key, "") for doc in documents],
                "top_n": top_n,
                "return_documents": False,
            },
        )
        response.raise_for_status()
        results = response.json()["results"]
    except httpx.RequestError as e:
        logger.warning(f"Reranker failed ({e}), returning top docs without reranking")
        return documents[:top_n]
    except Exception as e:
        logger.error(f"Unexpected reranker error: {e}")
        return documents[:top_n]

    reranked = []
    for r in results:
        if r["score"] < THRESHOLD:
            continue
        reranked.append(documents[r["index"]])

    if not reranked and documents:
        logger.info("All docs below threshold, picking top 1 as fallback")
        reranked = documents[:1]

    logger.info(f"Reranked {len(documents)} → {len(reranked)} docs (threshold={THRESHOLD})")
    return reranked
