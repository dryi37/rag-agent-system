import os
import json
import asyncio
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

load_dotenv()

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

client=QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY") or None,
)

vector_store = QdrantVectorStore(
    client=client,
    collection_name=os.getenv("QDRANT_COLLECTION", "rag_documents"),
    embedding=embeddings,
)

mcp = FastMCP("vector-search", host="0.0.0.0", port=8010)

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})

@mcp.tool()
async def search_internal_docs(query: str, top_k: int = 5) -> str:
    docs = await asyncio.to_thread(
        vector_store.similarity_search,
        query,
        k=top_k,
    )

    if not docs:
        return json.dumps([])

    results = [
        {
            "id": f"vector_{i}",
            "source": doc.metadata.get('source', 'internal'),
            "content": doc.page_content,
        }
        for i, doc in enumerate(docs)
    ]

    return json.dumps(results, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")