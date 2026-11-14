"""Streamlit chat UI for the BigBasket RAG assistant.

    streamlit run app.py
"""
import streamlit as st

from src import config
from src.rag import BigBasketRAG

st.set_page_config(page_title="BigBasket Product Assistant", page_icon="🛒")


@st.cache_resource(show_spinner="Loading product index…")
def load_rag():
    return BigBasketRAG()


rag = load_rag()

with st.sidebar:
    st.header("⚙️ Settings")
    mode = st.radio("Retrieval mode", ["hybrid", "vector"],
                    format_func=lambda m: "Hybrid (BM25 + vector)" if m == "hybrid" else "Vector only")
    k = st.slider("Chunks sent to the LLM (top-k)", 2, 12, config.TOP_K)
    st.caption(f"LLM: `{config.PRIMARY_MODEL}` via OpenRouter")
    st.caption(f"Embeddings: `{config.EMBED_MODEL}` · Vector store: FAISS")
    st.caption(f"Index: {rag.vectorstore.index.ntotal:,} chunks")
    if st.button("Clear chat"):
        st.session_state.messages = []

    st.divider()
    st.markdown("**Try asking:**")
    examples = [
        "What is the price of Saffola Gold oil?",
        "Compare Amul and Nestle milk products by price and rating",
        "Suggest a gluten-free snack under ₹150 and tell me its brand",
        "Which shampoos have the biggest discount?",
        "Do you deliver to Pune within 10 minutes?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.pending = ex

st.title("🛒 BigBasket Product Assistant")
st.caption("Ask about products, brands, prices, discounts and ratings. "
           "Answers come only from the BigBasket catalogue dataset (Kaggle, ~27k products).")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_sources(meta):
    if not meta:
        return
    label = f"📚 Sources ({len(meta['docs'])} chunks · best similarity {meta['best']:.2f})"
    with st.expander(label):
        if meta.get("filter") and meta["filter"] != [None, None]:
            st.caption(f"Price filter applied: {meta['filter']}")
        if meta.get("model"):
            st.caption(f"Answered by `{meta['model']}`")
        for d in meta["docs"]:
            m = d["meta"]
            st.markdown(f"**{m['product']}** — {m['brand']} · ₹{m['sale_price']:g} · "
                        f"{m['category']} › {m['type']}")
            st.caption(d["text"][:400] + ("…" if len(d["text"]) > 400 else ""))


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        render_sources(msg.get("sources"))

question = st.chat_input("Ask about any BigBasket product…")
if st.session_state.get("pending"):
    question = st.session_state.pop("pending")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching the catalogue…"):
            res = rag.answer(question, mode=mode, k=k)
        st.markdown(res.answer)
        sources = {
            "docs": [{"meta": d.metadata, "text": d.page_content} for d in res.docs],
            "best": res.best_score,
            "filter": list(res.price_filter),
            "model": res.model,
        }
        render_sources(sources)
    st.session_state.messages.append({"role": "assistant", "content": res.answer, "sources": sources})
