"""Objects shared by the Streamlit pages (cached once per server process)."""
import hashlib
from pathlib import Path

import streamlit as st


def _code_version() -> str:
    """Fingerprint of the pipeline code, so a redeploy never keeps answering with an old prompt."""
    h = hashlib.sha1()
    for name in ("rag.py", "config.py"):
        h.update((Path(__file__).parent / name).read_bytes())
    return h.hexdigest()[:12]


@st.cache_resource(show_spinner="Opening the store…", max_entries=1)
def _load_rag(version: str):
    import importlib

    import src.config
    import src.rag

    importlib.reload(src.config)
    return importlib.reload(src.rag).BigBasketRAG()


def load_rag():
    return _load_rag(_code_version())


@st.cache_resource(show_spinner=False)
def descriptions() -> dict[int, str]:
    """Full description per product (chunks joined), for the product-details view."""
    parts: dict[int, list[tuple[int, str]]] = {}
    for d in load_rag().vectorstore.docstore._dict.values():
        m = d.metadata
        text = d.page_content.split("Description:", 1)[-1].strip()
        parts.setdefault(m["product_id"], []).append((m["chunk"], text))
    return {pid: " ".join(t for _, t in sorted(chunks)) for pid, chunks in parts.items()}


def result_payload(res, mode: str) -> dict:
    """Serialisable summary of a RAGResult for the UIs."""
    from src import config

    return {
        "ids": list(dict.fromkeys(d.metadata["product_id"] for d in res.docs)),
        "meta": {
            "best": res.best_score, "threshold": config.RELEVANCE_THRESHOLD, "mode": mode,
            "fallback": res.used_fallback, "sub_queries": res.sub_queries, "filter": list(res.price_filter),
            "sort": list(res.sort) if res.sort else None, "model": res.model, "seconds": res.seconds,
        },
    }
