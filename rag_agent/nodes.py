import os
import logging
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from rag_agent.state import AgentState
from rag_agent.schemas import HallucinationDecision
from rag_agent.conversation import (
    format_history_for_prompt,
    summarize_history,
    RECENT_TOKEN_BUDGET,
)
from rag_agent.utils import _publish

load_dotenv()
logger = logging.getLogger(__name__)

# LLM 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)
hallucination_llm = llm.with_structured_output(HallucinationDecision)

# Node

async def process_history(state: AgentState, config: RunnableConfig) -> AgentState:
    await _publish(config, lambda p: p.status(state["thread_id"]))
    return {
        **state,
        "messages": [HumanMessage(content=state["query"])],
        "retrieved_docs": [],
        "hallucination_score": "no",
        "agent_iterations": 0,
        "iterations": 0,
    }


async def generate(state: AgentState, config: RunnableConfig) -> AgentState:
    await _publish(config, lambda p: p.generating(state["thread_id"]))

    docs = state.get("retrieved_docs", [])
    # print(f"GENERATE received {len(docs)} docs")
    # for i, doc in enumerate(docs):
    #     print(f"  doc[{i}] source={doc['source']} content[:50]={doc['content'][:50]}")
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
            await _publish(config, lambda p: p.token(state['thread_id'], token))

    return {
        **state,
        "generation": full_response,
        "messages": [AIMessage(content=full_response)],
        "iterations": state.get("iterations", 0) + 1,
    }


async def check_hallucination(state: AgentState, config: RunnableConfig) -> AgentState:
    await _publish(config, lambda p: p.hallucination_check(state["thread_id"]))
    docs = state.get("retrieved_docs", [])
    if not docs:
        return {**state, "hallucination_score": "no"}

    context = "\n\n".join([doc["content"] for doc in docs])

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Determine whether the answer contains information that is NOT supported by the provided documents.

Set has_hallucination = true if the answer includes fabricated facts, unsupported claims, or reasoning beyond the document content."""),
        ("human", "Documents:\n{context}\nAnswer:\n{answer}"),
    ])

    try:
        result: HallucinationDecision = await hallucination_llm.ainvoke(
            prompt.format_messages(context=context, answer=state["generation"])
        )
        score = "yes" if result.has_hallucination else "no"
        if score == "yes":
            logger.warning(f"Hallucination detected: {result.reason}")
    except Exception:
        score = "no"

    return {**state, "hallucination_score": score}


async def post_turn_cleanup(state: AgentState, config: RunnableConfig) -> AgentState:
    state_after_summary = await summarize_history(state)
    return {
        **state_after_summary
    }


# Conditional Edge 

def should_retry(state: AgentState) -> str:
    if state.get("iterations", 0) >= state.get("max_iterations", 3):
        return "end"
    if state.get("hallucination_score") == "yes":
        return "retry"
    return "end"
