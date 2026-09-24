"""Community Cloud entrypoint: public saved demo; opt-in protected live mode."""
from pathlib import Path
import hmac
import os
import runpy
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cloud_option(name, default=None):
    # Reading st.secrets materializes root-level TOML settings as environment
    # variables. Do not print this object, its values, or exception contents.
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


def is_enabled(value):
    return value is True or isinstance(value, str) and value.casefold() == "true"


live_enabled = is_enabled(cloud_option("RAG_CLOUD_LIVE_ENABLED", False))
os.environ["RAG_DEMO_ONLY"] = "0" if live_enabled else "1"

if live_enabled:
    # No model download, settings/key loading, or graph execution before access.
    access_code = cloud_option("RAG_CLOUD_ACCESS_CODE", "")
    if not isinstance(access_code, str) or len(access_code) < 16:
        st.error("Live mode needs a private access code of at least 16 characters.")
        st.stop()
    if not st.session_state.get("cloud_live_authorized"):
        st.title("Enterprise Policy Q&A · protected live demo")
        supplied_code = st.text_input("Private demo access code", type="password")
        if not supplied_code or not hmac.compare_digest(supplied_code.encode(), access_code.encode()):
            st.info("Live queries are restricted to protect the owner's remaining free API allowance.")
            st.stop()
        st.session_state["cloud_live_authorized"] = True

    # A local counter is not durable cloud accounting. Explicit owner approval
    # is needed before enabling, and before any redeployment can restore quota.
    if not is_enabled(cloud_option("RAG_CLOUD_BUDGET_ACKNOWLEDGED", False)):
        st.error("Live mode is locked until the owner confirms the shared API allowance and restart policy.")
        st.stop()
    from app.config import get_settings

    settings = get_settings()
    if not 1 <= settings.max_api_attempts <= 7:
        st.error("Set MAX_API_ATTEMPTS to the explicitly approved remaining allowance (at most 7).")
        st.stop()

    @st.cache_resource(show_spinner=False)
    def prepare_live_assets():
        from app.cloud_bootstrap import ensure_cloud_assets

        return ensure_cloud_assets(get_settings(), allow_download=True)

    with st.spinner("Preparing the approved local model and frozen policy index…"):
        try:
            prepare_live_assets()
        except Exception:
            st.error("Cloud setup did not complete. Check the committed frozen corpus and available resources. No API query was made.")
            st.stop()

# The standard interface implements clearly labelled saved replay when
# RAG_DEMO_ONLY=1. It never silently substitutes replay for a live response.
runpy.run_path(str(ROOT / "ui" / "streamlit_app.py"), run_name="__main__")
