"""Public result contract and internal LangGraph state (never contains secrets)."""
from typing import Any, Literal, TypedDict


class PolicyState(TypedDict, total=False):
    query: str
    status: Literal["answered", "fallback", "error"]
    answer: str
    citations: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    reason: str
    latency_seconds: float
    trace: list[str]
    api_called: bool
    draft: dict[str, Any]
    threshold: float

