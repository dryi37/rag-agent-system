import os
import json
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from langchain_tavily import TavilySearch
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

tavily = TavilySearch(max_results=7, tavily_api_key=os.getenv("TAVILY_API_KEY"))
splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    model_name="gpt-4o",
    chunk_size=400,
    chunk_overlap=50,
)

mcp = FastMCP("web-search", host="0.0.0.0", port=8011)

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})

@mcp.tool()
async def search_web(query: str) -> str:
    response = await tavily.ainvoke(query)

    results = response.get("results", []) if isinstance(response, dict) else response

    if not results:
        return json.dumps([])

    docs = []
    for i, r in enumerate(results):
        content = r.get("content", "")
        url = r.get("url", "web")
        chunks = splitter.split_text(content)
        for j, chunk in enumerate(chunks):
            docs.append({
                "id": f"web_{i}_{j}",
                "source": url,
                "content": chunk,
            })
    return json.dumps(docs, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")