from typing import Literal
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """
    Decision returned by the query router.
    Determines how the system should handle the user query.
    """
    route: Literal["direct", "vector", "web"] = Field(
        description=(
            "direct: The query can be answered directly without any external retrieval."
            "vector: Search internal indexed documents (RAG over internal knowledge base)."
            "web: Search external web sources for real-time or up-to-date information."
        )
    )
    reason: str = Field(description="A brief explanation for why this routing decision was chosen.")


class HallucinationDecision(BaseModel):
    """
    Decision returned by the hallucination checker.
    Evaluates whether the generated answer is grounded in the retrieved documents.
    """
    has_hallucination: bool = Field(
        description="True if the answer contains information that is not supported by the provided documents."
    )
    reason: str = Field(description="A short explanation describing why the answer is considered hallucinated or not.")