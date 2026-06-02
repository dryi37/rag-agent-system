import os
import json
import asyncio
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    Document,
)

load_dotenv()

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

client = AsyncQdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY") or None,
)

collection_name = os.getenv("QDRANT_COLLECTION", "rag_documentations")

# Verify collection exists (async)
async def verify_collection():
    try:
        await client.get_collection(collection_name)
        print(f"[INFO] Connected to collection: {collection_name}")
    except Exception as e:
        print(f"[WARN] Collection {collection_name} not found or error: {e}")

mcp = FastMCP("vector-search", host="0.0.0.0", port=8010)

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})

@mcp.tool()
async def search_internal_docs(
    query: str,
    top_k: int = 5,
) -> str:
    """
    Search internal documents using hybrid search (dense + sparse BM25 with RRF).

    Args:
        query: The search query
        top_k: Number of results to return (default 5)

    Returns:
        JSON string with results containing id, source, content, and score
    """
    if not query.strip():
        return json.dumps([])

    try:
        # Get query embedding (for dense vector)
        query_vector = embeddings.embed_query(query)

        # Hybrid search using Prefetch + RRF fusion
        results = await client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(
                    query=Document(text=query, model="Qdrant/bm25"),
                    using="sparse",
                    limit=top_k * 2,
                ),
                Prefetch(
                    query=query_vector,
                    using="dense",
                    limit=top_k * 2,
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        results_data = [
            {
                "id": str(hit.id),
                "source": hit.payload.get("metadata", {}).get("source", "internal"),
                "content": hit.payload.get("page_content", "").strip(),
                "score": hit.score,
            }
            for hit in results.points
        ]

        if not results_data:
            return json.dumps([])

        return json.dumps(results_data, ensure_ascii=False)

    except Exception as e:
        import traceback
        print(f"[ERROR] search failed: {e}")
        traceback.print_exc()
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    asyncio.run(verify_collection())
    mcp.run(transport="streamable-http")
