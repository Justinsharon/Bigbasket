"""Storefront page: an HTML/CSS/JS component backed by the RAG pipeline."""
import time
from pathlib import Path

import streamlit as st

from src.shared import descriptions, load_rag, result_payload

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

# Hide Streamlit's own chrome so the storefront fills the page.
st.markdown(
    """<style>
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"], footer { display: none !important; }
    [data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: 100% !important; }
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #f6f7f9; }
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_resource
def storefront():
    return st.components.v2.component(
        "basketbuddy_store",
        html="",
        css=(FRONTEND / "store.css").read_text(encoding="utf-8"),
        js=(FRONTEND / "store.js").read_text(encoding="utf-8"),
    )


rag = load_rag()
ss = st.session_state
ss.setdefault("store_chat", [])      # [{role, content, ids, meta}]
ss.setdefault("store_search", None)  # {q, ids, nonce}
ss.setdefault("store_details", {})   # {id: description}

noop = lambda: None  # noqa: E731
res = storefront()(
    key="store",
    data={"chat": ss.store_chat, "search": ss.store_search, "details": ss.store_details},
    on_search_change=noop, on_ask_change=noop, on_details_change=noop, on_nav_change=noop,
    on_clearchat_change=noop,
)

changed = False
if res.search:
    q = str(res.search.get("q", ""))[:200].strip()
    if q:
        docs, _, _ = rag.retrieve(q, mode="hybrid", k=60)
        ids = list(dict.fromkeys(d.metadata["product_id"] for d in docs))
        ss.store_search = {"q": q, "ids": ids, "nonce": res.search.get("nonce", time.time())}
        changed = True
if res.ask:
    q = str(res.ask.get("q", ""))[:500].strip()
    mode = res.ask.get("mode") if res.ask.get("mode") in ("hybrid", "vector") else "hybrid"
    if q:
        out = rag.answer(q, mode=mode)
        ss.store_chat = ss.store_chat + [
            {"role": "user", "content": q},
            {"role": "assistant", "content": out.answer, **result_payload(out, mode)},
        ]
        changed = True
if res.details is not None and res.details != "":
    pid = int(res.details)
    ss.store_details = {**ss.store_details, str(pid): descriptions().get(pid, "No description available.")}
    changed = True
if res.clearchat:
    ss.store_chat = []
    changed = True
if res.nav == "classic":
    st.switch_page("views/classic_chat.py")
if changed:
    st.rerun()
