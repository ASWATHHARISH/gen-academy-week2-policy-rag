"""Local Streamlit interface; only an explicit form submission runs the graph."""
from pathlib import Path
import sys
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.saved_demo import demo_only_enabled, load_saved_demo

st.set_page_config(page_title="Enterprise Policy Q&A", page_icon="📘", layout="centered")


def safe_source_url(value: object) -> str | None:
    """Only render source links from the public handbook, never model-made domains."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme == "https"
            and parsed.hostname == "handbook.gitlab.com"
            and parsed.path.startswith("/handbook/")
            and not parsed.username
            and not parsed.password
        ):
            return value
    except ValueError:
        pass
    return None


def show_source(metadata: dict, label: str = "Open source section") -> None:
    url = safe_source_url(metadata.get("section_url")) or safe_source_url(metadata.get("source_url"))
    if url:
        st.link_button(label, url)


def safe_error_message(error: Exception) -> str:
    """Do not display raw exceptions, request headers, keys, or stack traces."""
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "The local application dependencies are not ready. Complete the README setup steps and restart Streamlit."
    if isinstance(error, FileNotFoundError):
        return "The local model or document index is missing. Complete model download and ingestion, then try again."
    return "The question could not be processed. Check the local model, document index, and Gemini configuration, then retry. The README includes setup steps."


def run_once(question: str) -> dict:
    if demo_only_enabled():
        raise RuntimeError("Live generation is disabled in this demonstration deployment.")
    # Lazy import keeps setup guidance available before graph dependencies are ready.
    from app.graph import run_query

    return run_query(question)


def render_result(result: dict, *, saved: bool = False) -> None:
    status = result.get("status", "error")
    if status == "answered":
        st.success("Saved answer with validated source references" if saved else "Answer with validated source references")
    elif status == "fallback":
        st.info("The available evidence is insufficient for a supported answer.")
    else:
        st.error("The service could not complete this request. This is a technical issue, not a policy answer.")

    answer = result.get("answer")
    if isinstance(answer, str) and answer.strip() and status in {"answered", "fallback"}:
        st.markdown(answer)
    elif status == "error":
        st.write("Check the local model and document index, the API key in the local .env file, free-tier access, and available quota. Then retry.")

    latency = result.get("latency_seconds")
    if isinstance(latency, (int, float)) and latency >= 0:
        label = "Recorded response time from the saved run" if saved else "Response time"
        st.caption(f"{label}: {latency:.2f} s")

    evidence = result.get("evidence") or []
    evidence = [item for item in evidence if isinstance(item, dict)]
    evidence_by_id = {str(item.get("id")): item for item in evidence if item.get("id") is not None}
    citations = result.get("citations") or []
    if status == "answered" and citations:
        st.subheader("Sources")
        seen: set[tuple[str, str]] = set()
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            citation_id = str(citation.get("id") or citation.get("chunk_id") or citation.get("evidence_id") or "")
            matched = evidence_by_id.get(citation_id)
            metadata = matched.get("metadata", {}) if matched else citation.get("metadata", citation)
            if not isinstance(metadata, dict):
                continue
            # The graph validates citations; the UI further restricts links to
            # URLs present in the actual retrieved evidence.
            known_urls = {
                safe_source_url(item.get("metadata", {}).get(field))
                for item in evidence
                if isinstance(item.get("metadata"), dict)
                for field in ("source_url", "section_url")
            } - {None}
            url = safe_source_url(metadata.get("section_url")) or safe_source_url(metadata.get("source_url"))
            if not url or url not in known_urls:
                continue
            title = str(metadata.get("title") or metadata.get("document_id") or "Policy source")
            section = str(metadata.get("section") or "")
            identity = (url, section)
            if identity in seen:
                continue
            seen.add(identity)
            st.write(f"{citation.get('number', len(seen))}. {title}")
            if section:
                st.caption(section)
            show_source(metadata)

    if evidence:
        with st.expander(f"Inspect retrieved evidence ({len(evidence)} excerpts)"):
            st.caption("These are retrieved passages, not a confidence score. Some may have been rejected by the answer checks.")
            for number, item in enumerate(evidence, start=1):
                metadata = item.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                st.write(f"{number}. {metadata.get('title') or 'Policy excerpt'}")
                if metadata.get("section"):
                    st.caption(str(metadata["section"]))
                excerpt = str(item.get("text") or "")
                st.text(excerpt[:2200] + ("…" if len(excerpt) > 2200 else ""))
                show_source(metadata)
                if number < len(evidence):
                    st.divider()


st.title("Enterprise Policy Q&A")
st.caption("Explore a snapshot of GitLab’s public policies with traceable sources.")

demo_only = demo_only_enabled()
if demo_only:
    replay_mode = True
else:
    mode = st.sidebar.radio(
        "Mode", ["Live questions", "Saved evaluation replay"],
        index=1 if st.query_params.get("demo") == "1" else 0,
    )
    replay_mode = mode == "Saved evaluation replay"

saved_demo = None
if replay_mode:
    try:
        saved_demo = load_saved_demo()
    except (OSError, ValueError, TypeError):
        st.error("The saved demonstration results are unavailable. Restore the packaged P1 evaluation file.")

with st.sidebar:
    st.subheader("This collection")
    st.write("12 selected public policy documents")
    st.caption("HR · onboarding · IT/security · travel · compliance")
    st.divider()
    if replay_mode:
        st.write("Mode: saved evaluation replay")
        st.caption("No model loading or API requests in replay mode.")
        if saved_demo:
            st.write("Recorded retrieval: dense + BM25 hybrid (RRF)")
            st.caption(f"BGE-small · Chroma · {saved_demo['chunk_tokens']}/{saved_demo['overlap_tokens']} token chunks")
            st.write(f"Recorded generation: {saved_demo['model']}")
    else:
        try:
            from app.config import get_settings

            settings = get_settings()
            st.write("Retrieval: dense + BM25 hybrid (RRF)" if settings.retrieval_mode == "hybrid" else "Retrieval: local dense search")
            st.caption(f"BGE-small · Chroma · {settings.chunk_tokens}/{settings.overlap_tokens} token chunks")
            st.write(f"Generation: {settings.google_model}")
        except Exception:
            st.write("Generation: Gemini 3.5 Flash-Lite")
    st.divider()
    st.caption("A student demonstration based on public GitLab material. Answers describe the saved corpus; source pages may have changed.")
    st.link_button("Corpus license · CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/")

if replay_mode:
    st.subheader("Saved evaluation replay — not live")
    st.warning("SAVED RESULT — NOT A LIVE REQUEST. These are actual responses and evidence from the recorded P1 evaluation. No API call is made.")
    if demo_only:
        st.caption("This public deployment is demonstration-only. Live question submission is disabled.")
    if saved_demo:
        st.caption(f"Recorded run: {saved_demo['timestamp_utc']} · {saved_demo['source_file']}")
        examples = {example["id"]: example for example in saved_demo["examples"]}
        selected_id = st.selectbox(
            "Choose a saved question", list(examples),
            format_func=lambda question_id: f"{question_id} · {examples[question_id]['question']}",
        )
        if st.button("Show saved result", type="primary", use_container_width=True):
            selected = examples[selected_id]
            st.session_state["policy_saved_result"] = selected["response"]
            st.session_state["policy_saved_question"] = selected["question"]
        if "policy_saved_result" in st.session_state:
            st.divider()
            st.caption(f"Saved question: {st.session_state.get('policy_saved_question', '')}")
            render_result(st.session_state["policy_saved_result"], saved=True)
else:
    st.write("Ask a policy question. Each supported answer includes the passages used to produce it.")
    st.caption("Example: What is the minimum password length required by GitLab’s password standard?")

    with st.form("policy_question_form", clear_on_submit=False):
        question = st.text_area(
            "Your question",
            placeholder="For example, what should I do before booking a business trip?",
            max_chars=1500,
            height=110,
        )
        submitted = st.form_submit_button("Find an answer", type="primary", use_container_width=True)

    if submitted:
        cleaned = question.strip()
        if not cleaned:
            st.warning("Enter a policy question first.")
        else:
            with st.spinner("Finding relevant policy passages and checking the answer…"):
                try:
                    result = run_once(cleaned)
                    if not isinstance(result, dict):
                        raise TypeError("Unexpected graph result")
                    st.session_state["policy_result"] = result
                    st.session_state["policy_question"] = cleaned
                    st.session_state.pop("policy_ui_error", None)
                except Exception as error:
                    st.session_state["policy_ui_error"] = safe_error_message(error)
                    st.session_state.pop("policy_result", None)

    if st.session_state.get("policy_ui_error"):
        st.error(st.session_state["policy_ui_error"])

    if "policy_result" in st.session_state:
        st.divider()
        st.caption(f"Question: {st.session_state.get('policy_question', '')}")
        render_result(st.session_state["policy_result"])

st.caption("If a rule depends on your country, employment arrangement, or event, include that context. Missing evidence produces a fallback.")
