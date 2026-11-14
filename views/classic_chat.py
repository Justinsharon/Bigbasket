"""Classic Streamlit chat (st.chat_input) over the same RAG pipeline."""
import streamlit as st

from src import config
from src.images import image_for
from src.shared import load_rag, result_payload

rag = load_rag()
ss = st.session_state
ss.setdefault("classic_chat", [])

with st.sidebar:
    st.page_link("views/store.py", label="← Back to the store", icon="🧺")
    st.markdown("### Settings")
    mode = st.radio("Retrieval", ["hybrid", "vector"], horizontal=True,
                    format_func=lambda m: "Hybrid (BM25 + vector)" if m == "hybrid" else "Vector only")
    k = st.slider("Chunks sent to the LLM (top-k)", 2, 12, config.TOP_K)
    if st.button("Clear chat", use_container_width=True):
        ss.classic_chat = []
    st.caption(f"Embeddings `{config.EMBED_MODEL.split('/')[-1]}` · FAISS · threshold {config.RELEVANCE_THRESHOLD}")

st.title("💬 BasketBuddy: classic chat")
st.caption("The same RAG pipeline as the store, using Streamlit's built-in chat. "
           "Answers come only from the BigBasket catalogue dataset.")


def show(msg):
    st.markdown(msg["content"])
    meta = msg.get("meta") or {}
    if msg.get("docs") and not meta.get("fallback"):
        with st.expander(f"📚 Sources ({len(msg['docs'])} products)"):
            for m in msg["docs"]:
                e, _ = image_for(m)
                st.markdown(f"{e} **{m['product']}** · {m['brand']} · ₹{m['sale_price']:g}"
                            + (f" · {m['rating']}★" if m.get("rating") else " · Not rated"))
    with st.expander("🔍 Retrieval details"):
        st.json(meta, expanded=False)


for msg in ss.classic_chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"]) if msg["role"] == "user" else show(msg)

if q := st.chat_input("Ask about any product…"):
    ss.classic_chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("Searching the catalogue…"):
            out = rag.answer(q, mode=mode, k=k)
        msg = {"role": "assistant", "content": out.answer, "docs": [d.metadata for d in out.docs],
               "meta": result_payload(out, mode)["meta"]}
        show(msg)
    ss.classic_chat.append(msg)
