"""One bounded Gemini request with structured claims and local provenance checks."""
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.budget import BudgetError, reserve_attempt
from app.config import Settings, get_settings
from app.prompts import GROUNDING_SYSTEM


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    text: str


class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    chunk_ids: list[str]
    quotes: list[Quote]


class GroundedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sufficient: bool
    claims: list[GroundedClaim] = Field(default_factory=list)


class GenerationError(RuntimeError):
    def __init__(self, code: str, api_called: bool = False):
        super().__init__(code)
        self.code = code
        self.api_called = api_called


def provider_error_code(error: Exception) -> str:
    """Use numeric HTTP status only; never format provider messages or responses."""
    current: BaseException | None = error
    for _ in range(5):
        if current is None:
            break
        candidates = [getattr(current, "code", None), getattr(current, "status_code", None)]
        response = getattr(current, "response", None)
        if response is not None:
            candidates.append(getattr(response, "status_code", None))
        for status in candidates:
            if type(status) is not int:
                continue
            known = {
                400: "gemini_invalid_request", 401: "gemini_authentication_failed",
                403: "gemini_permission_denied", 404: "gemini_model_not_found",
                429: "gemini_rate_limited",
            }
            if status in known:
                return known[status]
            if 500 <= status <= 599:
                return "gemini_provider_unavailable"
        current = current.__cause__
    return "gemini_request_failed"


def generate(query: str, evidence: list[dict[str, Any]], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if not settings.gemini_free_tier_confirmed:
        raise GenerationError("free_tier_not_confirmed")
    if not settings.google_api_key.get_secret_value().strip():
        raise GenerationError("gemini_key_missing")
    if settings.google_model != "gemini-3.5-flash-lite":
        raise GenerationError("unapproved_model")
    if not evidence:
        raise GenerationError("generation_without_evidence")

    from langchain_google_genai import ChatGoogleGenerativeAI

    # Neither model construction nor structured-output setup performs a request.
    try:
        model = ChatGoogleGenerativeAI(
            model=settings.google_model, api_key=settings.google_api_key,
            vertexai=False, max_output_tokens=1536,
            # This integration maps max_retries to SDK TOTAL attempts. Zero
            # restores SDK defaults; one means one request and no retries.
            max_retries=1, timeout=45,
        )
        structured = model.with_structured_output(GroundedResponse, method="json_schema")
        payload = json.dumps({"question": query, "excerpts": [
            {"chunk_id": item["id"], "title": item.get("metadata", {}).get("title", ""),
             "section": item.get("metadata", {}).get("section", ""), "text": item["text"]}
            for item in evidence
        ]}, ensure_ascii=False)
    except Exception:
        raise GenerationError("gemini_client_configuration") from None
    try:
        reserve_attempt(settings)
    except BudgetError as error:
        raise GenerationError(str(error)) from None
    try:
        response = structured.invoke([("system", GROUNDING_SYSTEM), ("human", payload)])
        if isinstance(response, BaseModel):
            return response.model_dump()
        if isinstance(response, dict):
            return GroundedResponse.model_validate(response).model_dump()
        raise ValueError
    except Exception as error:
        # Provider errors may contain request headers/URLs. Never echo their text.
        raise GenerationError(provider_error_code(error), api_called=True) from None
