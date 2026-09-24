"""An explicit retrieve -> gate -> generate -> validate workflow."""
import time
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.citations import CitationValidationError, validate_and_render
from app.config import Settings, get_settings
from app.generation import GenerationError, generate
from app.prompts import ERROR_ANSWER, FALLBACK_ANSWER
from app.retrieval import RetrievalError, deduplicate_evidence, effective_threshold, retrieve
from app.state import PolicyState
from app.scope import personal_legal_entitlement


def build_graph(
    settings: Settings | None = None,
    retriever: Callable | None = None,
    generator: Callable | None = None,
):
    """Inject (query, settings) retriever and (query, evidence, settings) generator."""
    settings = settings or get_settings()
    retrieve_fn, generate_fn = retriever or retrieve, generator or generate

    def validation(state: PolicyState) -> dict[str, Any]:
        query = state.get("query", "")
        valid = isinstance(query, str) and bool(query.strip()) and len(query) <= 1500
        reason = "" if valid else "invalid_question"
        if valid and settings.gate_mode == "p1" and personal_legal_entitlement(query):
            reason = "personal_legal_entitlement_out_of_scope"
        return {"query": query.strip() if isinstance(query, str) else "",
                "reason": reason,
                "trace": [*state.get("trace", []), "validate_question"]}

    def retrieval(state: PolicyState) -> dict[str, Any]:
        trace = [*state["trace"], "retrieve_hybrid_rrf" if settings.retrieval_mode == "hybrid" else "retrieve_dense"]
        try:
            return {"evidence": retrieve_fn(state["query"], settings), "trace": trace}
        except RetrievalError as error:
            return {"status": "error", "reason": str(error), "evidence": [], "trace": trace}
        except Exception:
            return {"status": "error", "reason": "retrieval_unavailable", "evidence": [], "trace": trace}

    def gate(state: PolicyState) -> dict[str, Any]:
        trace = [*state["trace"], "evidence_gate"]
        if state.get("status") == "error":
            return {"trace": trace}
        try:
            threshold = effective_threshold(settings)
            candidates = [item for item in state.get("evidence", [])
                         if isinstance(item.get("score"), (int, float))
                         and -1 <= item["score"] <= 1]
            if settings.gate_mode == "p1":
                # This gates topical relevance, not factual support. Preserve
                # complementary passages so generation can check every part.
                selected = deduplicate_evidence(candidates, min(5, settings.evidence_k))
                supported = selected if any(item["score"] >= threshold for item in selected) else []
            else:
                supported = [item for item in candidates if item["score"] >= threshold]
            supported = deduplicate_evidence(supported, min(5, settings.evidence_k))
            return {"evidence": supported, "threshold": threshold, "trace": trace,
                    "reason": "" if supported else "insufficient_retrieval_evidence"}
        except Exception:
            return {"status": "error", "reason": "invalid_evidence_configuration", "trace": trace}

    def generation(state: PolicyState) -> dict[str, Any]:
        trace = [*state["trace"], "grounded_generation"]
        try:
            draft = generate_fn(state["query"], state["evidence"], settings)
            return {"draft": draft, "api_called": True, "trace": trace}
        except GenerationError as error:
            return {"status": "error", "reason": error.code, "api_called": error.api_called, "trace": trace}
        except Exception:
            return {"status": "error", "reason": "generation_unavailable", "trace": trace}

    def citations(state: PolicyState) -> dict[str, Any]:
        trace = [*state["trace"], "validate_citations"]
        try:
            answer, sources = validate_and_render(state.get("draft", {}), state["evidence"])
            return {"status": "answered", "answer": answer, "citations": sources,
                    "reason": "", "trace": trace}
        except CitationValidationError as error:
            return {"status": "fallback", "reason": str(error), "trace": trace}
        except Exception:
            return {"status": "fallback", "reason": "invalid_generation", "trace": trace}

    def fallback(state: PolicyState) -> dict[str, Any]:
        answer = FALLBACK_ANSWER
        if state.get("reason") == "personal_legal_entitlement_out_of_scope":
            answer = ("I can't determine personal legal entitlements from this company-policy snapshot. "
                      "Please check the applicable jurisdiction and employment terms with HR or qualified counsel.")
        return {"status": "fallback", "answer": answer, "citations": [],
                "trace": [*state["trace"], "fallback"]}

    def error_response(state: PolicyState) -> dict[str, Any]:
        return {"status": "error", "answer": ERROR_ANSWER, "citations": [],
                "trace": [*state["trace"], "error_response"]}

    workflow = StateGraph(PolicyState)
    for name, function in [
        ("validate_question", validation), ("retrieve", retrieval), ("evidence_gate", gate),
        ("generate", generation), ("validate_citations", citations),
        ("fallback", fallback), ("error_response", error_response),
    ]:
        workflow.add_node(name, function)
    workflow.add_edge(START, "validate_question")
    workflow.add_conditional_edges("validate_question", lambda s: "fallback" if s.get("reason") else "retrieve")
    workflow.add_edge("retrieve", "evidence_gate")
    workflow.add_conditional_edges("evidence_gate", lambda s: (
        "error_response" if s.get("status") == "error" else "fallback" if s.get("reason") else "generate"
    ))
    workflow.add_conditional_edges("generate", lambda s: "error_response" if s.get("status") == "error" else "validate_citations")
    workflow.add_conditional_edges("validate_citations", lambda s: END if s.get("status") == "answered" else "fallback")
    workflow.add_edge("fallback", END)
    workflow.add_edge("error_response", END)
    return workflow.compile()


def run_query(query: str, settings: Settings | None = None, *, retriever=None, generator=None) -> dict[str, Any]:
    start = time.perf_counter()
    initial: PolicyState = {"query": query, "answer": "", "citations": [], "evidence": [],
                            "reason": "", "trace": [], "api_called": False, "latency_seconds": 0.0}
    result = dict(build_graph(settings, retriever=retriever, generator=generator).invoke(initial))
    result.pop("draft", None)
    result["latency_seconds"] = round(time.perf_counter() - start, 4)
    return result
