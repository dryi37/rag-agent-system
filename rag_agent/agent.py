import os
import json
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from rag_agent.state import AgentState
from rag_agent.inference_clients import rerank_documents
from rag_agent.conversation import format_history_for_prompt, RECENT_TOKEN_BUDGET
from rag_agent.utils import _publish

from rag_agent.langfuse.prompts import get_system_prompt

load_dotenv()
logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = int(os.getenv("MAX_REACT_ITERATIONS", "3"))
TOOL_TIMEOUT = float(os.getenv("TOOL_TIMEOUT", "15"))
RERANK_TOP_N_PER_SOURCE = int(os.getenv("RERANK_TOP_N_PER_SOURCE", "3"))  

# llm
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
    )

# mcp client config
MCP_SERVERS_CONFIG = {
    "vector_search": {
        "url": os.getenv("MCP_VECTOR_SEARCH_URL", "http://vector-search-svc:8010/mcp"),
        "transport": "streamable_http",
    },
    "web_search": {
        "url": os.getenv("MCP_WEB_SEARCH_URL", "http://web-search-svc:8011/mcp"),
        "transport": "streamable_http",
    },
}

# mcp client singleton

_mcp_client: Optional[MultiServerMCPClient] = None
_llm_with_tools = None
_tools_by_name: dict = {}

async def init_mcp_client():
    global _mcp_client, _llm_with_tools, _tools_by_name
    _mcp_client = MultiServerMCPClient(MCP_SERVERS_CONFIG)
    tools = await _mcp_client.get_tools()
    _tools_by_name = {t.name: t for t in tools}
    _llm_with_tools = llm.bind_tools(tools)
    logger.info(f"MCP client initialized with {len(tools)} tools: {[t.name for t in tools]}")
 
 
async def close_mcp_client():
    global _mcp_client
    _mcp_client = None
    logger.info("MCP client closed")

# --helper
def _parse_tool_results_to_docs(tool_name: str, tool_content) -> list[dict]:
    if isinstance(tool_content, list):
        tool_content = next(
            (item['text'] for item in tool_content if item.get('type') == 'text'), ""
        )
    if not tool_content:
        return []
    try:
        items = json.loads(tool_content)
        return [
            {
                "content": item.get("content", ""),
                "source": item.get("source", "unknown"),
                "type": tool_name,
            }
            for item in items if item.get("content")
        ]
    except json.JSONDecodeError:
        logger.warning(f"Tool {tool_name} returned non-json, falling back to empty")
        return []


# react agent node
async def react_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    if _mcp_client is None or _llm_with_tools is None:
        raise RuntimeError("MCP client is not initialized. Call init_mcp_client() at startup.")
    await _publish(config, lambda p: p.agent_thinking(state["thread_id"], state["query"]))

    history_str = format_history_for_prompt(
        state.get("messages", []),
        summary=state.get("conversation_summary"),
        recent_token_budget=RECENT_TOKEN_BUDGET,
    )

    system_prompt = get_system_prompt(history_str)
    
    docs_by_tool: dict[str, list[dict]] = {}
    agent_messages = [HumanMessage(content=state["query"])]
    iterations = 0


    while iterations < MAX_REACT_ITERATIONS:
        iterations += 1

        try:
            response = await _llm_with_tools.ainvoke(
                [{"role": "system", "content": system_prompt}] + agent_messages
            )
        except Exception as e:
            logger.error(f"LLM invoke failed at iteration {iterations}: {e}")
            break

        agent_messages.append(response)

        if not response.tool_calls:
            logger.info(f"Agent finished after {iterations} iterations (no more tool calls)")
            break

        tool_results = []
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            logger.info(f"[Iteration {iterations}] Calling tool: {tool_name}({tool_args})")
            await _publish(config, lambda p: p.tool_started(state["thread_id"], tool_name))

            try:
                result = await asyncio.wait_for(
                    _tools_by_name[tool_name].ainvoke(tool_args),
                    timeout=TOOL_TIMEOUT
                )
                content = result
                await _publish(config, lambda p: p.tool_done(state["thread_id"], tool_name))

            except asyncio.TimeoutError:
                logger.warning(f"Tool {tool_name} timed out")
                content = f"Tool timeout: {tool_name} took longer than {TOOL_TIMEOUT}s"
                await _publish(config, lambda p: p.error(state["thread_id"], f"Tool {tool_name} timeout"))

            except Exception as e:
                logger.warning(f"Tool {tool_name} failed: {e}")
                content = f"Tool error: {str(e)}"
                await _publish(config, lambda p: p.error(state["thread_id"], f"Tool {tool_name} failed: {str(e)}"))

            new_docs = _parse_tool_results_to_docs(tool_name, content)
            if new_docs:
                docs_by_tool.setdefault(tool_name, []).extend(new_docs)
                snippets = "\n".join([
                    f"- [{doc['source']}]: {doc['content'][:100].strip()}..."
                    for doc in new_docs
                ])
                summary = f"Found {len(new_docs)} results:\n{snippets}"
            else:
                summary = "No results found"

            tool_results.append(
                ToolMessage(content=summary, tool_call_id=tool_call["id"])
            )

        agent_messages.extend(tool_results)

    if not docs_by_tool:
        logger.warning("Agent collected no documents")
        return {**state, "retrieved_docs": []}

    retrieved_docs = []
    for tool_name, docs in docs_by_tool.items():
        # print(f"BEFORE RERANK [{tool_name}]: {len(docs)} docs")
        try:
            top_docs = await rerank_documents(
                query=state["query"],
                documents=docs,
                top_n=RERANK_TOP_N_PER_SOURCE,
            )
        except Exception as e:
            logger.warning(f"Rerank failed for {tool_name}: {e}")
            top_docs = docs[:RERANK_TOP_N_PER_SOURCE]
        # print(f"AFTER RERANK [{tool_name}]: {len(top_docs)} docs")
        retrieved_docs.extend(top_docs)
    # print(f"TOTAL retrieved_docs passed to generate: {len(retrieved_docs)}")

    logger.info(
        f"Agent done: {iterations} iterations, "
        f"sources: {list(docs_by_tool.keys())}, "
        f"retrieved: {len(retrieved_docs)} docs"
    )

    return {
        **state,
        "retrieved_docs": retrieved_docs,
        "agent_iterations": iterations,
    }
