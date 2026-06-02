# Agentic RAG

A production-ready Agentic RAG system built with LangGraph, Gemini, Qdrant, and Redis. The agent uses a ReAct loop with MCP tools to retrieve, rerank, and generate answers with hallucination checking.

## Architecture

```
Client
  │
  ▼
FastAPI (main.py)
  │  POST /threads/{id}/messages  → agent runs in background
  │  GET  /threads/{id}/events    → SSE stream (Redis Streams)
  │
  ▼
LangGraph Agent
  process_history → react_agent → generate → check_hallucination
                         │
                    MCP Tools (HTTP)
                    ├── vector_search  → Qdrant Cloud
                    ├── web_search     → Tavily
                    └── database_search → Postgres
                         │
                    Reranker (BGE-v2-m3)
                         │
                    Redis Streams (event bus)
```

**Managed services (no self-hosting):**
- Postgres → [Supabase](https://supabase.com) (conversation history via LangGraph checkpointer)
- Qdrant → [Qdrant Cloud](https://qdrant.tech/cloud) (vector store)

**Self-hosted:**
- Redis (semantic cache + Redis Streams event bus)
- Reranker (BAAI/bge-reranker-v2-m3, GPU)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | LangGraph |
| LLM | Gemini (Google) |
| Vector DB | Qdrant Cloud |
| Reranker | BGE-Reranker-v2-m3 |
| Tool protocol | MCP (Streamable HTTP) |
| Event bus | Redis Streams |
| Semantic cache | Redis + Gemini embeddings |
| Conversation persistence | Postgres (Supabase) |
| API | FastAPI + SSE |

## Project Structure

```
.
├── main.py                        # FastAPI app, SSE endpoints
├── graph.py                       # LangGraph graph builder
├── agent.py                       # ReAct agent + MCP client
├── nodes.py                       # LangGraph nodes
├── state.py                       # AgentState definition
├── schemas.py                     # Pydantic schemas
├── conversation.py                # Sliding window summarization
├── inference_clients.py           # Reranker HTTP client
├── ingest.py                      # Document ingestion script
├── redis_modules/
│   ├── cache.py                   # Semantic cache
│   └── streams.py                 # Redis Streams event publisher/subscriber
├── mcp_servers/
│   ├── vector_search.py           # MCP server: Qdrant search
│   ├── web_search.py              # MCP server: Tavily web search
│   └── database_search.py        # MCP server: Postgres query
├── services/reranker/
│   └── main.py                    # BGE reranker HTTP service
├── k8s/                           # Kubernetes manifests
├── Dockerfile                     # App image
├── docker-compose.yml             # Local dev
├── docker-compose.prod.yml        # Production
└── Makefile                       # Build & run shortcuts
```

## Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- GPU (optional, for reranker)

### 1. Managed Services

**Supabase (Postgres):**
1. Create account at https://supabase.com
2. New project → Settings → Database → Connection string → URI
3. Copy the connection string

**Qdrant Cloud:**
1. Create account at https://qdrant.tech/cloud
2. Create cluster (free tier)
3. Copy URL and API key

**Tavily:**
1. Create account at https://tavily.com
2. Copy API key

**Gemini:**
1. Get API key at https://aistudio.google.com/apikey

### 2. Environment

```bash
cp .env.example .env
# Fill in all API keys
```

### 3. Ingest Documents

The ingest script creates a Qdrant collection with both dense (Gemini) and sparse (BM25) vector configurations.

```bash
pip install -r requirements.txt

mkdir docs
# Add your PDF or .txt files to docs/

python ingest.py --source ./docs --collection rag_documents
```

**Important**: The collection must have `sparse_vectors_config` for BM25. The script automatically creates it with the correct configuration. If you need to re-index with a new configuration, use `recreate=True` (default behavior).

After ingestion, the system is ready for hybrid search.

### 4. Run Local

```bash
# Build images
make build

# Run (CPU)
make up

# Run (GPU)
make up-gpu

# View logs
make logs
```

### 5. Test

```bash
# Create thread
curl -X POST http://localhost:8000/threads

# Subscribe SSE (open in separate terminal FIRST)
curl -N http://localhost:8000/threads/{thread_id}/events

# Send message
curl -X POST http://localhost:8000/threads/{thread_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"query": "your question here"}'
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/threads` | Create new thread |
| `POST` | `/threads/{id}/messages` | Send message, agent runs in background |
| `GET` | `/threads/{id}/events` | SSE stream — receive agent events |
| `GET` | `/health` | Health check |
| `DELETE` | `/cache` | Clear semantic cache |

### MCP Tools

The agent uses MCP (Model Context Protocol) tools for retrieval:

**`search_internal_docs`** - Hybrid search (dense + sparse with RRF)
- `query` (string, required): Search query
- `top_k` (int, optional): Number of results (default: 5)

The tool always uses hybrid search combining:
- **Dense**: Gemini embeddings (semantic)
- **Sparse**: BM25 (keyword)
- **Fusion**: Reciprocal Rank Fusion (RRF)

### SSE Events

```json
{"type": "status",   "data": {"status": "retrieving"}}
{"type": "status",   "data": {"status": "generating"}}
{"type": "retrying", "data": {"iteration": 1}}
{"type": "done",     "data": {"answer": "...", "sources": [...], "iterations": 2}}
{"type": "error",    "data": {"message": "..."}}
```

## Production Deploy

```bash
# Build and push images
make push

# Run production
make prod-up        # CPU
make prod-up-gpu    # GPU
```

Production uses managed Postgres (Supabase) and Qdrant Cloud — only Redis and the reranker are self-hosted.

## Key Design Decisions

**Why MCP over direct tool calls?**
Each retrieval source runs as an independent service — easier to scale, update, and deploy separately.

**Why Redis Streams over Pub/Sub?**
Streams persist events — clients can reconnect with `last_event_id` and resume without missing events. Pub/Sub is fire-and-forget.

**Why async job + SSE over HTTP streaming?**
Decouples the request lifecycle from the agent execution. Client can disconnect and reconnect without losing results.

**Why managed Postgres/Qdrant?**
Stateful services should not run on K8s without proper operators. Managed services handle backup, failover, and scaling automatically.

## Hybrid Search

The system implements **advanced hybrid search** combining dense vector embeddings (Gemini) with sparse BM25 keyword search using **Reciprocal Rank Fusion (RRF)**:

### Architecture

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Embed   │  (Gemini)
    └────┬────┘
         │
    ┌────▼───────────────────────────────┐
    │   Qdrant Query with Prefetch       │
    │                                    │
    │  Prefetch[0]: Sparse (BM25)       │
    │    - Compute BM25 from query text │
    │    - using="sparse"               │
    │    - limit = top_k * 2            │
    │                                    │
    │  Prefetch[1]: Dense (Vector)      │
    │    - Gemini embedding             │
    │    - using="dense"                │
    │    - limit = top_k * 2            │
    │                                    │
    │  Fusion: RRF (Reciprocal Rank)    │
    └────┬──────────────────────────────┘
         │
    ┌────▼────────────┐
    │  Top-K Results  │
    └─────────────────┘
```

### Collection Configuration

Hybrid search requires a Qdrant collection with both dense and sparse vector configs:

```python
vectors_config={
    "dense": VectorParams(size=3072, distance=COSINE)  # Gemini embedding
}
sparse_vectors_config={
    "sparse": SparseVectorParams(modifier=Modifier.IDF)  # BM25 with IDF
}
```

The system uses `on_disk_payload=True` to enable BM25 text indexing.

### Usage

The `search_internal_docs` MCP tool supports hybrid mode:

```json
{
  "query": "machine learning pipeline",
  "top_k": 5,
  "hybrid": true
}
```

- `hybrid=false`: Pure dense vector search (semantic)
- `hybrid=true`: Hybrid search (dense + sparse + RRF fusion)

### Re-indexing

Hybrid search requires the collection to have both vector types. Re-run ingestion:

```bash
python ingest.py --source ./docs --collection rag_documents
```

The ingest script automatically creates the collection with the correct configuration.