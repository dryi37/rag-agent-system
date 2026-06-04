# RAG Agent System

A production-grade **Retrieval-Augmented Generation** (RAG) agent system that combines hybrid vector search, web search, and a ReAct agent loop with reranking to deliver context-aware, citation-backed answers. Built with **FastAPI**, **LangGraph**, **LangChain**, and deployed via **Docker Compose**.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-black)
![LangGraph](https://img.shields.io/badge/LangGraph-orange)
![Qdrant](https://img.shields.io/badge/Qdrant-red)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

---

## Architecture

```
                         ┌──────────────────────────────────────┐
                         │           FastAPI Backend             │
                         │         (LangGraph Agent)             │
                         └──────┬───────────────┬──────────────┘
                                │               │
              ┌──────────────────┘               └──────────────────┐
              │                                                       │
     ┌────────▼────────┐                                   ┌────────▼────────┐
     │   PostgreSQL    │                                   │      Redis       │
     │  (Checkpointing │                                   │  (Semantic Cache)│
     │  + Auth Store)  │                                   └─────────────────┘
     └─────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
     ┌────────▼────────┐ ┌─────▼──────┐ ┌────────▼──────────┐
     │  MCP: Vector    │ │  MCP: Web  │ │   Reranker Svc    │
     │  Search (Qdrant)│ │  Search    │ │  (GPU-accelerated) │
     │  Hybrid: Dense  │ │  (Tavily)  │ │  Jina / BGE-M3    │
     │  + BM25 RRF     │ │            │ └───────────────────┘
     └───────┬──────────┘ └───────────┘
             │
     ┌───────▼────────────────┐
     │        Qdrant           │
     │   Vector Database       │
     │   (Hybrid Collections)  │
     └─────────────────────────┘
```

### RAG Pipeline Flow

```
 User Query
    │
    ▼
 ┌────────────────────┐
 │  Semantic Cache    │  ← Redis cosine similarity check
 │  (cache hit?)      │
 └────┬───────────────┘
      │ miss
      ▼
 ┌────────────────────┐
 │  ReAct Agent Loop  │  ← up to N iterations via LangGraph
 │  ┌──────────────┐  │
 │  │ Tool Call 1  │──┼──▶ MCP Vector Search (hybrid Qdrant)
 │  │ Tool Call 2  │──┼──▶ MCP Web Search (Tavily)
 │  └──────────────┘  │
 └────┬───────────────┘
      │ collected docs
      ▼
 ┌────────────────────┐
 │  Reranker Service  │  ← GPU microservice (cross-encoder)
 │  top-k per source  │
 └────┬───────────────┘
      │ ranked docs
      ▼
 ┌────────────────────┐
 │  Generation (LLM)  │  ← Gemini 2.5 Flash + conversation context
 │  Streaming output  │
 └────┬───────────────┘
      │
      ▼
 ┌────────────────────┐
 │  Post-Turn Cleanup │  ← sliding-window summarization
 │  Store in Cache    │
 └────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.11+, FastAPI, Uvicorn |
| **Agent Framework** | LangGraph (StateGraph), LangChain |
| **LLM** | Google Gemini 2.5 Flash |
| **Embeddings** | Gemini Embedding 001 (3072-dim) |
| **Vector DB** | Qdrant v1.9.2 (dense + sparse BM25 hybrid) |
| **Relational DB** | PostgreSQL 16 (async via psycopg3) |
| **Cache** | Redis 7 (semantic cache with cosine similarity) |
| **Reranker** | GPU microservice (Jina / BGE-M3 cross-encoder) |
| **Observability** | Langfuse (LLM tracing, span-level metrics) |
| **Auth** | JWT (access + refresh token rotation, bcrypt) |
| **MCP** | Model Context Protocol (streamable HTTP transport) |
| **Web Search** | Tavily API |
| **Deployment** | Docker Compose |

---

## Key Features

### Hybrid Retrieval
Documents are indexed with **dual embeddings** — dense vectors (Gemini) and sparse BM25 vectors — then fused at query time via **Reciprocal Rank Fusion (RRF)**. This combines semantic understanding with keyword matching.

### ReAct Agent with Tool Calling
The agent iteratively calls retrieval tools (up to `MAX_REACT_ITERATIONS` rounds), collects results from multiple sources, and decides when sufficient context is gathered before generating the final answer.

### GPU-Accelerated Reranking
A standalone reranker microservice re-scores retrieved documents using a cross-encoder, filtering by relevance threshold to ensure only high-quality context reaches the LLM.

### Semantic Caching
Redis-backed semantic cache stores query-answer pairs. On cache hit, cosine similarity between the incoming query embedding and cached embeddings (threshold: 0.92) short-circuits the entire retrieval pipeline.

### Sliding-Window Context Management
Conversation history is managed with a token budget. Older messages are summarized via LLM while recent messages are preserved in full, enabling long-running multi-turn conversations.

### Streaming & Observability
Responses are streamed token-by-token via Server-Sent Events. Every LLM call is traced in **Langfuse** with input/output, latency, and token usage.

### JWT Authentication
Full auth flow with access tokens (15-min expiry) and refresh token rotation (3-day expiry). Tokens are stored and validated against PostgreSQL.

---

## Project Structure

```
rag-agent-system/
├── backend/
│   ├── main.py                      # FastAPI app, lifespan, routers
│   ├── state.py                     # AgentState TypedDict (LangGraph)
│   ├── schemas.py                   # Pydantic request/response models
│   ├── dependencies.py              # FastAPI dependency injection
│   ├── core/
│   │   ├── db.py                    # Async PostgreSQL connection pool
│   │   └── security.py              # JWT, bcrypt password hashing
│   ├── routers/
│   │   ├── auth.py                  # /auth/* — register, login, refresh, logout
│   │   └── chat.py                  # /threads/* — create thread, send message (SSE)
│   ├── crud/
│   │   ├── user.py                  # User CRUD
│   │   ├── token.py                 # Refresh token CRUD
│   │   └── thread.py                # Thread & message persistence
│   ├── agent/
│   │   ├── agent.py                 # ReAct agent node (tool loop, reranking)
│   │   ├── graph.py                 # LangGraph StateGraph definition + checkpointer
│   │   ├── nodes.py                 # Graph nodes: process_history, generate, cleanup
│   │   ├── runner.py                # Streaming execution with Langfuse + cache
│   │   ├── conversation.py          # Token-budgeted history formatting & summarization
│   │   └── inference_clients.py     # Reranker HTTP client
│   ├── langfuse/
│   │   ├── client.py                # Langfuse singleton
│   │   ├── handler.py               # Callback handler for LangGraph
│   │   └── prompts.py               # System prompt management
│   └── redis_modules/
│       ├── cache.py                 # SemanticCache (cosine similarity match)
│       └── __init__.py              # Redis client singleton
├── mcp_server/
│   ├── vector_search.py             # MCP tool: hybrid Qdrant search (RRF fusion)
│   └── web_search.py                # MCP tool: Tavily web search + text splitting
├── services/
│   └── reranker/
│       └── main.py                  # Reranker microservice (FastAPI + cross-encoder)
├── training/
│   ├── preprocessing/
│   │   ├── dataset.py               # Dataset loading & preparation
│   │   └── split_data.py            # Train/validation splitting
│   └── reranker/
│       ├── reranker_hf.py           # HuggingFace reranker wrapper
│       ├── fine_tune_Jina.py         # Jina reranker fine-tuning pipeline
│       └── fine_tune_bge_base.py     # BGE-M3 reranker fine-tuning pipeline
├── docs/                            # Reference PDFs for ingestion
├── ingest.py                        # Document ingestion script (PDF/TXT → Qdrant)
├── docker-compose.yaml              # Development compose
├── docker-compose.prod.yaml         # Production compose (healthchecks, init SQL)
└── .env                             # Environment configuration
```

---

## API Reference

### Authentication

```http
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
```

### Chat

```http
POST /threads                     # Create a new conversation thread
POST /threads/{thread_id}/messages # Send a message (SSE streaming response)
```

#### SSE Event Types

| Event Type | Description |
|---|---|
| `status` | Agent status update (thinking, searching, generating) |
| `token` | Streaming generation token |
| `cache_hit` | Semantic cache hit with cached answer |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Google Gemini API key
- Tavily API key (for web search)
- Langfuse keys (optional, for observability)

### Environment Variables

```bash
# Core
GEMINI_API_KEY=                    # Google AI Studio key
SECRET_KEY=                         # JWT signing secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=3

# Data Stores
POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag_agent
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333

# External Services
RERANKER_SERVICE_URL=http://localhost:8002
TAVILY_API_KEY=                    # Tavily search API
LANGFUSE_PUBLIC_KEY=               # Optional: observability
LANGFUSE_SECRET_KEY=               # Optional: observability

# MCP Servers
MCP_VECTOR_SEARCH_URL=http://localhost:8010/mcp
MCP_WEB_SEARCH_URL=http://localhost:8011/mcp
```

### Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd rag-agent-system
cp .env.example .env   # fill in your keys

# 2. Start all services
docker compose up -d

# 3. Ingest documents into Qdrant
python ingest.py --source ./docs --collection rag_documentations

# 4. Start the reranker (GPU required)
docker compose --profile gpu up -d reranker

# 5. Run the API
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Document Ingestion

```bash
python ingest.py \
  --source ./docs \
  --collection rag_documentations \
  --chunk-size 400 \
  --chunk-overlap 50
```

---

## Design Decisions

- **LangGraph StateGraph** for the agent loop — explicit node transitions, built-in checkpointing, and streaming support via `astream`.
- **MCP (Model Context Protocol)** for tool abstraction — retrieval tools are self-contained HTTP services discoverable by the agent, making it trivial to add new data sources.
- **PostgreSQL checkpointer** for LangGraph — conversation state persists across sessions with full history reconstruction.
- **Separate reranker microservice** — keeps the main API stateless regarding model loading; GPU isolation prevents OOM on the inference server.
- **Semantic cache with cosine similarity** — catches near-duplicate queries without requiring exact string matches, reducing LLM cost for common questions.

---

## License

MIT
