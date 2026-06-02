import os
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import StateGraph, END
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from rag_agent.state import AgentState
from rag_agent.agent import react_agent
from rag_agent.nodes import (
    process_history,
    generate,
    check_hallucination,
    post_turn_cleanup,
    should_retry,
)


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    graph.add_node("process_history", process_history)
    graph.add_node("react_agent", react_agent)
    graph.add_node("generate", generate)
    graph.add_node("check_hallucination", check_hallucination)
    graph.add_node("post_turn_cleanup", post_turn_cleanup)

    graph.set_entry_point("process_history")
    graph.add_edge("process_history", "react_agent")
    graph.add_edge("react_agent", "generate")
    graph.add_edge("generate", "check_hallucination")

    graph.add_conditional_edges(
        "check_hallucination",
        should_retry,
        {
            "retry": "react_agent",
            "end": "post_turn_cleanup",
        }
    )

    graph.add_edge("post_turn_cleanup", END)

    return graph.compile(checkpointer=checkpointer)


_pool = None
_checkpointer = None

async def get_checkpointer():
    global _pool, _checkpointer

    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        print("[WARNING] POSTGRES_URL not setup -> use in-memory")
        return None

    if _checkpointer is None:
        _pool = AsyncConnectionPool(
            conninfo=postgres_url,
            kwargs={
                "prepare_threshold": None,
                "autocommit": True, 
                "row_factory": dict_row
            }, 
            open=False,
        )
        await _pool.open()
        _checkpointer = AsyncPostgresSaver(_pool)
        await _checkpointer.setup()

    return _checkpointer

async def close_checkpointer():
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.__aexit__(None, None, None)
        _pool = None
        _checkpointer = None


_graph = None

async def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(await get_checkpointer())
    return _graph