import os
import logging
from dotenv import load_dotenv

from langgraph.config import get_stream_writer
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from backend.state import AgentState
from backend.agent.conversation import (
    format_history_for_prompt,
    summarize_history,
    RECENT_TOKEN_BUDGET,
)

load_dotenv()
logger = logging.getLogger(__name__)

# LLM 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)
# hallucination_llm = llm.with_structured_output(HallucinationDecision)

# Node

async def process_history(state: AgentState, config: RunnableConfig) -> AgentState:
    return {
        **state,
        "messages": [HumanMessage(content=state["query"])],
        "retrieved_docs": [],
        "agent_iterations": 0,
    }


async def generate(state: AgentState, config: RunnableConfig) -> AgentState:
    writer = get_stream_writer()
    writer({"type": "status", "message": "Đang tạo câu trả lời..."})
    docs = state.get("retrieved_docs", [])
    history_str = format_history_for_prompt(
        state.get("messages", []),
        summary=state.get("conversation_summary"),
        recent_token_budget=RECENT_TOKEN_BUDGET,
    )

    context = (
        "\n---\n".join([
            f"[{doc['type'].upper()} | {doc['source']}]\n{doc['content']}"
            for doc in docs[:6]
        ])
        if docs else None
    )

    input_variables = {
        "history": history_str or "(New conversation)",
        "query": state["query"]
    }

    if context:
        input_variables["context"] = context
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent assistant. Answer strictly based on the provided documents and conversation history.

- Provide accurate information using ONLY the provided documents
- Cite sources using [source] when referencing document content
- Use conversation history to maintain continuity when relevant
- Respond in the user's language"""),
            ("human", "Documents:\n{context}\n---\nConversation History:\n{history}\n---\nQuestion: {query}"),
        ])

    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent assistant. Answer based on conversation history and your general knowledge.

- Provide a natural and coherent response
- Reference prior conversation if relevant
- Respond in the user's language"""),
            ("human", "Conversation History:\n{history}\n---\nQuestion: {query}"),
        ])

    full_response = ""
    async for chunk in llm.astream(prompt.format_messages(**input_variables)):
        token = chunk.content
        if token:
            full_response += token

    return {
        **state,
        "generation": full_response,
        "messages": [AIMessage(content=full_response)],
    }

async def post_turn_cleanup(state: AgentState, config: RunnableConfig) -> AgentState:
    state_after_summary = await summarize_history(state)
    return {
        **state_after_summary
    }
