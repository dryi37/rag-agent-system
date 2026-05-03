import os
from typing import Optional
from dotenv import load_dotenv
import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from rag_agent.state import AgentState

load_dotenv()

# -- Token budegt --
HISTORY_TOKEN_BUDGET = int(os.getenv("HISTORY_TOKEN_BUDGET", 2000))
RECENT_TOKEN_BUDGET = int(os.getenv("RECENT_TOKEN_BUDGET", 1500))
SUMMARY_TOKEN_BUDGET = HISTORY_TOKEN_BUDGET - RECENT_TOKEN_BUDGET

_enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken"""
    return len(_enc.encode(text))

def count_message_tokens(msg: BaseMessage) -> int:
    """
    Count tokens of a single message, including role overhead
    (approximately 4 tokens per message).
    """
    return count_tokens(str(msg.content)) + 4  # +4 cho role prefix


def count_messages_tokens(messages: list[BaseMessage]) -> int:
    """Return total token count of a list of messages."""
    return sum(count_message_tokens(m) for m in messages)

#--llm--
_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)

#-- Helper--

def format_history_for_prompt(
    messages: list[BaseMessage],
    summary: Optional[str] = None,
    recent_token_budget: int = RECENT_TOKEN_BUDGET,
) -> str:
    parts = []

    if summary:
        summary_block = f"[Previous conversation summary]\n{summary}"
        parts.append(summary_block)

    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    recent_parts = []
    used_tokens = 0
    for msg in reversed(non_system):
        token_count = count_message_tokens(msg)
        if used_tokens + token_count > recent_token_budget:
            break
        if isinstance(msg, HumanMessage):
            recent_parts.insert(0, f"Human: {msg.content}")
        elif isinstance(msg, AIMessage):
            recent_parts.insert(0, f"Assistant: {msg.content}")
        used_tokens += token_count

    parts.extend(recent_parts)
    return "\n".join(parts) if parts else ""

# -- Sliding Window Summarization --
async def summarize_history(state: AgentState) -> AgentState:
    messages = state.get("messages", [])
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    if count_messages_tokens(non_system) <= HISTORY_TOKEN_BUDGET:
        return state

    to_keep, used = [], 0
    for msg in reversed(non_system):
        t = count_message_tokens(msg)
        if used + t > RECENT_TOKEN_BUDGET:
            break
        to_keep.insert(0, msg)
        used += t

    keep_ids = set(id(m) for m in to_keep)
    to_summarize = [m for m in non_system if id(m) not in keep_ids]

    if not to_summarize:
        return state

    history_to_summarize = "\n".join([
        f"{'Human' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in to_summarize
    ])

    existing_summary = state.get("conversation_summary", "")
    if existing_summary:
        history_to_summarize = (
            f"[Previous summary]\n{existing_summary}\n\n"
            f"[New conversation content]\n{history_to_summarize}"
        )

    prompt = ChatPromptTemplate.from_messages([
    ("system", """Summarize the following conversation.

Keep:
- Main topics discussed
- Important information provided by the user
- Key decisions or conclusions

Output requirements:
- One concise paragraph
- No bullet points
- Be compact and information-dense"""),
    ("human", "{history}")
])

    try:
        response = await _llm.ainvoke(
            prompt.format_messages(history=history_to_summarize),
            config={"max_output_tokens": SUMMARY_TOKEN_BUDGET}
        )
        new_summary = response.content.strip()

    except Exception:
        return state

    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    return {
        **state,
        "messages": system_msgs + to_keep,
        "conversation_summary": new_summary,
    }
