import logging

from langfuse import propagate_attributes
from langchain_core.messages import AIMessageChunk

from backend.langfuse.handler import get_langfuse_handler
from backend.langfuse.client import langfuse
from backend.core.db import get_db_pool
from backend.crud.thread import save_message


logger = logging.getLogger(__name__)

async def run_agent(thread_id, query, user_id, graph, semantic_cache):
    cached = await semantic_cache.get(query)
    if cached:
        yield {"type": "cache_hit", "answer": cached["answer"], "sources": cached.get("sources", [])}
        return
        
    langfuse_handler = get_langfuse_handler()

    with langfuse.start_as_current_observation(
        as_type="span", 
        name="rag agent",
        input={"query": query}
    ) as span:
        with propagate_attributes(
            session_id=thread_id,
            user_id=user_id or "anonymous",
            tags=["dev"],
        ):
            initial_state = {
                "query": query,
                "thread_id": thread_id,
                "generation": "",
            }
            config = {
                "configurable": {"thread_id": thread_id,},
                "callbacks": [langfuse_handler],
            }

            final_state = None

            async for part in graph.astream(
                initial_state, 
                config=config,
                stream_mode=["messages", "updates", "custom"],
                version="v2",
            ):
                if part["type"] == "messages":
                    msg, metadata = part["data"]
                    if (
                        isinstance(msg, AIMessageChunk)
                        and msg.content 
                        and metadata.get("langgraph_node") == "generate"
                    ):
                        yield {"type": "token", "content": msg.content}

                elif part["type"] == "custom":
                    yield part["data"]
                
                elif part["type"] == "updates":
                    if "generate" in part["data"]:
                        final_state = part["data"]["generate"]

            sources = [
                {"source": doc.get("source", ""), "type": doc.get("type", "")}
                for doc in final_state.get("retrieved_docs", [])
            ]

            span.update(
                output={
                    "answer": final_state.get("generation"),
                    "sources": sources,
                }
            )

            await semantic_cache.set(
                query=query,
                answer=final_state["generation"],
                metadata={"sources": sources},
            )

            async with get_db_pool().connection() as db:
                await save_message(
                    db,
                    thread_id=thread_id,
                    role="assistant",
                    content=final_state["generation"],
                    sources=sources,
                )