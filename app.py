"""BigBasket Product Assistant: Streamlit frontend for the RAG chatbot.

    streamlit run app.py
"""
import html
from collections import Counter

import streamlit as st

from src import config
from src.rag import BigBasketRAG

st.set_page_config(page_title="BigBasket Product Assistant", page_icon="🛒", layout="wide")

# --------------------------------------------------------------------------- styles
st.markdown(
    """
<style>
:root { --bb-green:#84c225; --bb-dark:#3d6b0f; --bb-red:#d63b3b; --muted:#6b7280; }
.block-container { padding-top: 3.6rem; max-width: 1100px; }
div[data-testid="stButton"] button { height: auto; min-height: 2.6rem; padding: 6px 10px; }
div[data-testid="stButton"] button * { white-space: normal !important; overflow: visible !important;
    text-overflow: clip !important; text-align: left; font-size: .82rem; line-height: 1.25; }
.hero { background: linear-gradient(120deg, #3d6b0f 0%, #84c225 100%); color: #fff;
        border-radius: 16px; padding: 22px 26px; margin-bottom: 14px; }
.hero h1 { color:#fff; font-size: 1.7rem; margin: 0 0 4px 0; padding: 0; }
.hero p { margin: 0; opacity: .92; font-size: .95rem; }
.chips { margin-top: 12px; display:flex; gap:8px; flex-wrap:wrap; }
.chip { background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35);
        padding: 3px 10px; border-radius: 999px; font-size: .78rem; }
.pcard { border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: 10px 12px;
         height: 100%; background: rgba(132,194,37,.04); margin-bottom: 10px; }
.pcard .brand { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
.pcard .name { font-weight: 600; font-size: .88rem; line-height: 1.25; margin: 2px 0 6px 0;
               display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.pcard .price { font-weight: 700; font-size: 1.02rem; }
.pcard .mrp { text-decoration: line-through; color: var(--muted); font-size: .78rem; margin-left: 4px; }
.pcard .off { background: var(--bb-red); color: #fff; font-size: .68rem; font-weight: 700;
              padding: 1px 6px; border-radius: 6px; margin-left: 6px; vertical-align: middle; }
.pcard .meta { font-size: .74rem; color: var(--muted); margin-top: 6px; }
.pcard .rating { background: var(--bb-dark); color: #fff; font-size: .7rem; font-weight: 700;
                 padding: 1px 6px; border-radius: 6px; }
.pcard .norating { color: var(--muted); font-size: .7rem; }
.fallback { border-left: 4px solid #f59e0b; padding: 2px 0 2px 12px; }
.small-muted { color: var(--muted); font-size: .8rem; }
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- data
@st.cache_resource(show_spinner="Loading 30k product chunks and search indexes…")
def load_rag():
    return BigBasketRAG()


@st.cache_data(show_spinner=False)
def catalogue_stats():
    docs = list(load_rag().vectorstore.docstore._dict.values())
    products = {d.metadata["product_id"]: d.metadata for d in docs}
    cats = Counter(m["category"] for m in products.values())
    brands = len({m["brand"] for m in products.values()})
    return len(products), len(docs), brands, cats


rag = load_rag()
n_products, n_chunks, n_brands, cats = catalogue_stats()

EXAMPLES = {
    "🔎 Factual": ["What is Himalaya Neem Face Wash used for?", "What is the price of Saffola Gold oil?"],
    "⚖️ Compare": ["Which is cheaper: Maggi noodles or Yippee noodles?",
                  "Compare Tata Tea and Red Label tea on price and rating"],
    "🧩 Multi-part": ["Suggest a gluten-free snack under ₹150 and tell me its brand and rating",
                     "Which baby diapers have the highest discount, and what is their rating?"],
    "🏷️ Deals": ["What is the cheapest basmati rice?", "Best rated green tea"],
    "🚫 Not in data": ["Do you deliver to Pune within 10 minutes?", "What is BigBasket's return policy?"],
}

# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    mode = st.radio(
        "Retrieval mode", ["hybrid", "vector"], horizontal=True,
        format_func=lambda m: "Hybrid (BM25 + vector)" if m == "hybrid" else "Vector only",
        help="Switch to 'Vector only' to see what keyword search adds.",
    )
    k = st.slider("Products sent to the LLM (top-k)", 2, 12, config.TOP_K)
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []

    st.markdown("### 🧾 Catalogue")
    c1, c2 = st.columns(2)
    c1.metric("Products", f"{n_products:,}")
    c2.metric("Brands", f"{n_brands:,}")
    with st.expander("Categories"):
        for cat, n in cats.most_common():
            st.markdown(f"<span class='small-muted'>{html.escape(cat)}</span> — **{n:,}**",
                        unsafe_allow_html=True)

    with st.expander("🛠️ How it works"):
        st.markdown(
            f"""
1. **Data**: Kaggle BigBasket catalogue, cleaned to {n_products:,} products
2. **Chunking**: one document per product (header + description); long ones split at
   {config.CHUNK_SIZE} chars / {config.CHUNK_OVERLAP} overlap → {n_chunks:,} chunks
3. **Embeddings**: `{config.EMBED_MODEL.split('/')[-1]}` (local, 384-d)
4. **Vector store**: FAISS (cosine)
5. **Retrieval**: hybrid BM25 + FAISS, fused with RRF; comparison questions are split into
   sub-queries; price filters and sorting use metadata
6. **Guardrail**: similarity below {config.RELEVANCE_THRESHOLD} → "not in catalogue"
7. **LLM**: grounded prompt → OpenRouter / Gemini (automatic fallback)
"""
        )
    st.caption("Data: Kaggle *BigBasket Entire Product List* (CC BY-NC-SA 4.0). Prices are a dataset "
               "snapshot. This is a student project, not affiliated with BigBasket.")

# --------------------------------------------------------------------------- header
st.markdown(
    f"""
<div class="hero">
  <h1>🛒 BigBasket Product Assistant</h1>
  <p>Ask about groceries, brands, prices, discounts and ratings. Every answer comes from the product
  catalogue, and the bot tells you when the catalogue doesn't have the answer.</p>
  <div class="chips">
    <span class="chip">{n_products:,} products</span><span class="chip">{len(cats)} categories</span>
    <span class="chip">Hybrid RAG</span><span class="chip">Grounded answers</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------------------------------- render helpers
def product_card(m: dict) -> str:
    price = f"₹{m['sale_price']:,.2f}".rstrip("0").rstrip(".")
    mrp = off = ""
    if m["market_price"] > m["sale_price"]:
        mrp = f"<span class='mrp'>₹{m['market_price']:,.2f}</span>".replace(".00<", "<")
        if m.get("discount_pct"):
            off = f"<span class='off'>{m['discount_pct']:.0f}% OFF</span>"
    rating = (f"<span class='rating'>{m['rating']:.1f} ★</span>" if m.get("rating")
              else "<span class='norating'>Not rated</span>")
    return f"""
<div class="pcard">
  <div class="brand">{html.escape(m['brand'])}</div>
  <div class="name" title="{html.escape(m['product'])}">{html.escape(m['product'])}</div>
  <div><span class="price">{price}</span>{mrp}{off}</div>
  <div class="meta">{rating} &nbsp;·&nbsp; {html.escape(m['type'])}</div>
</div>"""


def render_products(sources: dict):
    docs = sources.get("docs") or []
    if not docs or sources.get("fallback"):
        return
    st.markdown("<div class='small-muted'>Products used to answer</div>", unsafe_allow_html=True)
    cols_per_row = 3
    for i in range(0, len(docs), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, d in zip(cols, docs[i:i + cols_per_row]):
            col.markdown(product_card(d["meta"]), unsafe_allow_html=True)


def render_details(s: dict):
    with st.expander("🔍 Retrieval details"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Best similarity", f"{s['best']:.2f}",
                  help=f"Cosine similarity of the closest chunk. Below {config.RELEVANCE_THRESHOLD} → fallback.")
        c2.metric("Mode", s["mode"])
        c3.metric("Chunks", len(s["docs"]))
        c4.metric("Time", f"{s['seconds']:.1f}s")
        notes = []
        if s.get("sub_queries"):
            notes.append("**Query decomposition:** " + " · ".join(f"`{q}`" for q in s["sub_queries"]))
        if s.get("filter") and s["filter"] != [None, None]:
            lo, hi = s["filter"]
            notes.append(f"**Price filter:** ₹{lo or 0} – {('₹' + str(hi)) if hi else 'any'}")
        if s.get("sort"):
            field, desc = s["sort"]
            notes.append(f"**Sorted by:** {field.replace('_', ' ')} ({'high → low' if desc else 'low → high'})")
        if s.get("model"):
            notes.append(f"**Answered by:** `{s['model']}`")
        if s.get("fallback"):
            notes.append("**Guardrail:** similarity below threshold, so the LLM was not called.")
        for n in notes:
            st.markdown(n)
        st.markdown("**Retrieved chunks (sent to the LLM as context):**")
        for d in s["docs"]:
            st.caption(d["text"][:500] + ("…" if len(d["text"]) > 500 else ""))


def render_assistant(content: str, sources: dict | None):
    if sources and sources.get("fallback"):
        st.markdown(f"<div class='fallback'>{html.escape(content)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(content)
    if sources:
        render_products(sources)
        render_details(sources)


# --------------------------------------------------------------------------- chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🛒"):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_assistant(msg["content"], msg.get("sources"))

# Welcome screen with example questions
if not st.session_state.messages:
    st.markdown("#### 👋 Try one of these")
    groups = list(EXAMPLES.items())
    cols = st.columns(len(groups))
    for col, (label, qs) in zip(cols, groups):
        col.markdown(f"**{label}**")
        for q in qs:
            if col.button(q, key=f"ex-{q}", use_container_width=True):
                st.session_state.pending = q
                st.rerun()

# --------------------------------------------------------------------------- input / answer
question = st.chat_input("Ask about any product, e.g. “healthy breakfast cereals under ₹200”")
if st.session_state.get("pending"):
    question = st.session_state.pop("pending")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🛒"):
        with st.spinner("Searching the catalogue…"):
            res = rag.answer(question, mode=mode, k=k)
        sources = {
            "docs": [{"meta": d.metadata, "text": d.page_content} for d in res.docs],
            "best": res.best_score,
            "filter": list(res.price_filter),
            "model": res.model,
            "mode": mode,
            "fallback": res.used_fallback,
            "sub_queries": res.sub_queries,
            "sort": res.sort,
            "seconds": res.seconds,
        }
        render_assistant(res.answer, sources)
    st.session_state.messages.append({"role": "assistant", "content": res.answer, "sources": sources})
