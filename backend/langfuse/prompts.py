import logging
from langfuse import get_client

logger = logging.getLogger(__name__)

langfuse = get_client()


def get_system_prompt(history_str: str) -> str:
    try:
        prompt = langfuse.get_prompt("rag_system_prompt", cache_ttl_seconds=300)
        return prompt.compile(history=history_str or "(New conversation)")
    except Exception as e:
        logger.warning(f"Failed to fetch prompt from Langfuse, using fallback: {e}")
        return _get_fallback_prompt(history_str)


def _get_fallback_prompt(history_str: str) -> str:
    return f"""You are an Agentic RAG assistant.

Your objective is to provide accurate, well-grounded answers by deciding whether to:
1. Answer directly from existing knowledge
2. Retrieve information using available tools

Conversation history:
{history_str or "(New conversation)"}

Tool usage strategy:
- search_internal_docs: internal documents, policies, domain-specific knowledge
- search_web: real-time information, news, recent updates

Decision Strategy:
1. Answer directly if the question can be answered confidently using general knowledge.
2. Use `search_internal_docs` for internal documentation or domain-specific information.
3. Use `search_web` for recent or external information not likely in internal sources.
4. Stop retrieving once enough information is collected to answer accurately.
"""