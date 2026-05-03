from typing import TypedDict, List, Literal, Annotated, Optional, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: Optional[str]

    thread_id: str    
    query: str

    agent_iterations: int
    retrieved_docs: List[Dict[str, Any]]

    generation: str
    hallucination_score: Literal["yes", "no"]
    
    iterations: int
    max_iterations: int