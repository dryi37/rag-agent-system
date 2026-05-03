"""
MCP Servers cho Agentic RAG.

Mỗi server chạy độc lập như subprocess, giao tiếp qua stdio:
  vector_search.py   -> search_internal_docs (Qdrant)
  web_search.py      -> search_web (Tavily)

Agent (agent.py) khởi động tất cả servers qua MultiServerMCPClient,
bind tools vào LLM, và chạy ReAct loop.
"""