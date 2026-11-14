"""BasketBuddy: an AI shopping assistant over the BigBasket product catalogue (Kaggle).

Original store-style UI (browse, search, filter) with a RAG chatbot panel.
    streamlit run app.py
"""
import html

import pandas as pd
import streamlit as st

from src import config
from src.images import CATEGORY_EMOJI, image_for, image_path
from src.rag import BigBasketRAG

st.set_page_config(page_title="BasketBuddy · AI grocery assistant", page_icon="🧺", layout="wide")
PAGE_SIZE = 12

# =========================================================================== styles
st.markdown(
    """
<style>
:root { --teal:#0f766e; --teal-dark:#115e59; --amber:#f59e0b; --rose:#e11d48; --muted:#6b7280;
        --line: rgba(120,120,120,.22); }
.block-container { padding-top: 3.2rem; max-width: 1400px; }
.topbar { display:flex; align-items:center; gap:14px; background: linear-gradient(90deg,#0f766e,#14b8a6);
          color:#fff; border-radius:16px; padding:12px 20px; margin-bottom:12px; }
.topbar img { width:46px; height:46px; }
.topbar .brand { font-size:1.55rem; font-weight:800; letter-spacing:-.02em; line-height:1; }
.topbar .brand span { color:#fde68a; }
.topbar .tag { font-size:.85rem; opacity:.92; }
.topbar .stats { margin-left:auto; display:flex; gap:8px; flex-wrap:wrap; }
.topbar .chip { background: rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35);
                border-radius:999px; padding:3px 10px; font-size:.75rem; white-space:nowrap; }
.sec { font-weight:700; font-size:1.02rem; margin: 6px 0 4px 0; }
.muted { color:var(--muted); font-size:.82rem; }
/* category tiles */
.cat { text-align:center; border:1px solid var(--line); border-radius:14px; padding:8px 4px 4px;
       background:#f8fbfa; }
.cat img { width:44px; height:44px; }
.cat div { font-size:.72rem; line-height:1.15; margin-top:4px; min-height:2.1em; }
/* product cards */
.card { border:1px solid var(--line); border-radius:14px; padding:10px 12px 8px; background:#fff;
        height:100%; position:relative; }
.card .imgbox { background: radial-gradient(circle at 50% 45%, #ecfdf5 0%, #f3f4f6 70%);
                border-radius:10px; height:118px; display:flex; align-items:center; justify-content:center; }
.card .imgbox img { width:84px; height:84px; filter: drop-shadow(0 6px 8px rgba(0,0,0,.15)); }
.card .off { position:absolute; top:16px; left:16px; background:var(--rose); color:#fff; font-size:.68rem;
             font-weight:800; padding:2px 7px; border-radius:7px; }
.card .brand { font-size:.68rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-top:8px; }
.card .name { font-weight:600; font-size:.86rem; line-height:1.25; height:2.5em; overflow:hidden;
              display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
.card .row { display:flex; align-items:baseline; gap:6px; margin-top:6px; }
.card .price { font-weight:800; font-size:1.02rem; }
.card .mrp { text-decoration:line-through; color:var(--muted); font-size:.76rem; }
.card .meta { display:flex; justify-content:space-between; align-items:center; margin-top:6px; font-size:.72rem;
              color:var(--muted); }
.rating { background:var(--teal); color:#fff; font-weight:700; font-size:.7rem; padding:1px 6px; border-radius:6px;
          white-space:nowrap; }
.card .meta > span:first-child { white-space:nowrap; flex:none; }
.card .type { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; margin-left:8px; text-align:right; }
/* compact cards in the assistant */
.mini { display:flex; gap:8px; align-items:center; border:1px solid var(--line); border-radius:10px;
        padding:6px 8px; margin-bottom:6px; background:#fff; }
.mini img { width:36px; height:36px; flex:none; }
.mini .t { font-size:.78rem; line-height:1.2; }
.mini .t b { font-size:.8rem; }
.fallback { border-left:4px solid var(--amber); padding:2px 0 2px 10px; }
.assist-head { display:flex; align-items:center; gap:8px; font-weight:800; font-size:1.05rem; }
.assist-head img { width:30px; height:30px; }
div[data-testid="stButton"] button { min-height:2.2rem; }
div[data-testid="stButton"] button p { font-size:.8rem; }
.foot { color:var(--muted); font-size:.75rem; text-align:center; margin-top:18px; }
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================================== data
@st.cache_resource(show_spinner="Loading the catalogue and search indexes…")
def load_rag():
    return BigBasketRAG()


@st.cache_data(show_spinner=False)
def load_products() -> pd.DataFrame:
    """One row per product, built from the FAISS docstore (first chunk of each product)."""
    rows = {}
    for d in load_rag().vectorstore.docstore._dict.values():
        m = d.metadata
        if m["chunk"] == 0:
            desc = d.page_content.split("Description:", 1)[-1].strip()
            rows[m["product_id"]] = {**m, "description": desc}
    df = pd.DataFrame(rows.values()).set_index("product_id", drop=False)
    imgs = [image_for(r) for r in df.to_dict("records")]
    df["emoji"] = [e for e, _ in imgs]
    df["img"] = [u for _, u in imgs]
    return df


@st.cache_data(show_spinner=False, max_entries=200)
def search_ids(query: str) -> list[int]:
    docs, _, _ = load_rag().retrieve(query, mode="hybrid", k=60)
    return list(dict.fromkeys(d.metadata["product_id"] for d in docs))


rag = load_rag()
products = load_products()
categories = products["category"].value_counts()

ss = st.session_state
ss.setdefault("messages", [])
ss.setdefault("category", "All")
ss.setdefault("page", 0)
ss.setdefault("ai_ids", None)


def money(x: float) -> str:
    return f"₹{x:,.2f}".replace(".00", "")


def img_tag(url, emoji, size):
    if url:
        return f"<img src='{url}' alt='{emoji}' style='width:{size}px;height:{size}px'>"
    return f"<span style='font-size:{int(size * .8)}px'>{emoji}</span>"


def product_card(r: dict) -> str:
    off = f"<div class='off'>{r['discount_pct']:.0f}% OFF</div>" if r["discount_pct"] >= 1 else ""
    mrp = f"<span class='mrp'>{money(r['market_price'])}</span>" if r["market_price"] > r["sale_price"] else ""
    rating = (f"<span class='rating'>{r['rating']:.1f} ★</span>" if pd.notna(r.get("rating")) and r.get("rating")
              else "<span>Not rated</span>")
    return f"""<div class="card">{off}
  <div class="imgbox">{img_tag(r['img'], r['emoji'], 84)}</div>
  <div class="brand">{html.escape(r['brand'])}</div>
  <div class="name" title="{html.escape(r['product'])}">{html.escape(r['product'])}</div>
  <div class="row"><span class="price">{money(r['sale_price'])}</span>{mrp}</div>
  <div class="meta">{rating}<span class="type">{html.escape(r['type'])}</span></div>
</div>"""


def mini_card(m: dict) -> str:
    e, url = image_for(m)
    rating = f" · {m['rating']:.1f}★" if m.get("rating") else " · Not rated"
    off = f" · <b style='color:#e11d48'>{m['discount_pct']:.0f}% off</b>" if m.get("discount_pct", 0) >= 1 else ""
    return (f"<div class='mini'>{img_tag(url, e, 36)}<div class='t'><b>{html.escape(m['product'])}</b><br>"
            f"{html.escape(m['brand'])} · {money(m['sale_price'])}{off}{rating}</div></div>")


# =========================================================================== product dialog
@st.dialog("Product details", width="large")
def show_product(pid: int):
    r = products.loc[pid].to_dict()
    c1, c2 = st.columns([1, 2])
    c1.markdown(f"<div class='card'><div class='imgbox' style='height:180px'>{img_tag(r['img'], r['emoji'], 130)}"
                "</div></div>", unsafe_allow_html=True)
    c2.caption(f"{r['category']} › {r['sub_category']} › {r['type']}")
    c2.markdown(f"### {r['product']}")
    c2.markdown(f"**Brand:** {r['brand']}")
    price = f"**{money(r['sale_price'])}**"
    if r["market_price"] > r["sale_price"]:
        price += f" ~~{money(r['market_price'])}~~ · :red[**{r['discount_pct']:.0f}% off**]"
    c2.markdown(price)
    c2.markdown(f"**Rating:** {r['rating']:.1f} ★" if pd.notna(r["rating"]) else "**Rating:** Not rated")
    st.markdown("**Description**")
    st.write(r["description"])
    if st.button("🤖 Ask BasketBuddy about this product", type="primary", use_container_width=True):
        ss.pending = f"Tell me about {r['product']} by {r['brand']}: what is it, its price and rating?"
        st.rerun()


# =========================================================================== sidebar: filters + AI settings
with st.sidebar:
    st.markdown("### 🔎 Filters")
    pmax = float(round(products["sale_price"].quantile(0.99), -2))
    price = st.slider("Price (₹)", 0.0, pmax, (0.0, pmax), step=10.0)
    min_rating = st.select_slider("Minimum rating", options=[0.0, 3.0, 3.5, 4.0, 4.5], value=0.0,
                                  format_func=lambda v: "Any" if v == 0 else f"{v}★ +")
    only_deals = st.toggle("Only discounted items")
    sort = st.selectbox("Sort by", ["Relevance", "Price: low to high", "Price: high to low",
                                    "Discount", "Rating"])
    st.divider()
    st.markdown("### 🤖 Assistant settings")
    mode = st.radio("Retrieval", ["hybrid", "vector"], horizontal=True,
                    format_func=lambda m: "Hybrid" if m == "hybrid" else "Vector only",
                    help="Hybrid = BM25 keyword search + FAISS vector search, fused with RRF.")
    k = st.slider("Products sent to the LLM (top-k)", 2, 12, config.TOP_K)
    if st.button("🗑️ Clear chat", use_container_width=True):
        ss.messages = []
    with st.expander("🛠️ How the assistant works"):
        st.markdown(
            f"""
1. **Data**: Kaggle BigBasket catalogue, cleaned to {len(products):,} products
2. **Chunking**: one document per product (header + description); long ones split at
   {config.CHUNK_SIZE} chars / {config.CHUNK_OVERLAP} overlap
3. **Embeddings**: `{config.EMBED_MODEL.split('/')[-1]}` (local, 384-d)
4. **Vector store**: FAISS (cosine)
5. **Retrieval**: hybrid BM25 + FAISS (RRF); comparisons split into sub-queries;
   price filters and sorting use metadata
6. **Guardrail**: similarity < {config.RELEVANCE_THRESHOLD} → "not in catalogue"
7. **LLM**: grounded prompt → OpenRouter / Gemini (automatic fallback)
"""
        )

# =========================================================================== top bar
logo = image_path("🧺")
st.markdown(
    f"""<div class="topbar">{img_tag(logo, '🧺', 46)}
  <div><div class="brand">Basket<span>Buddy</span></div>
  <div class="tag">AI shopping assistant for the BigBasket product catalogue</div></div>
  <div class="stats"><span class="chip">{len(products):,} products</span>
  <span class="chip">{products['brand'].nunique():,} brands</span><span class="chip">{len(categories)} categories</span>
  <span class="chip">RAG · grounded answers</span></div></div>""",
    unsafe_allow_html=True,
)

shop, assistant = st.columns([3, 2], gap="large")

# =========================================================================== shop column
with shop:
    q = st.text_input("Search", placeholder="Search products, brands or needs, e.g. “organic honey”, "
                      "“shampoo for dry hair”", label_visibility="collapsed", key="search")

    # Category tiles
    st.markdown("<div class='sec'>Shop by category</div>", unsafe_allow_html=True)
    cats = ["All", *categories.index]
    for row_start in range(0, len(cats), 6):
        cols = st.columns(6)
        for col, cat in zip(cols, cats[row_start:row_start + 6]):
            e = "🧺" if cat == "All" else CATEGORY_EMOJI.get(cat, "🛒")
            n = len(products) if cat == "All" else categories[cat]
            col.markdown(f"<div class='cat'>{img_tag(image_path(e), e, 44)}<div>{html.escape(cat)}</div></div>",
                         unsafe_allow_html=True)
            label = ("✓ " if ss.category == cat else "") + f"{n:,}"
            if col.button(label, key=f"cat-{cat}", use_container_width=True,
                          type="primary" if ss.category == cat else "secondary"):
                ss.category, ss.page, ss.ai_ids = cat, 0, None
                st.rerun()

    # Build the product list
    if ss.ai_ids:
        view = products.loc[[i for i in ss.ai_ids if i in products.index]]
        title = "🤖 Products from your last assistant answer"
    elif q.strip():
        view = products.loc[search_ids(q.strip())]
        title = f"Results for “{q.strip()}”"
    else:
        view = products.sort_values(["rating", "discount_pct"], ascending=False, na_position="last")
        title = "Top rated picks"
    if ss.category != "All" and not ss.ai_ids:
        view = view[view["category"] == ss.category]
        title += f" in {ss.category}"
    view = view[(view["sale_price"] >= price[0]) & ((view["sale_price"] <= price[1]) | (price[1] >= pmax))]
    if min_rating:
        view = view[view["rating"].fillna(0) >= min_rating]
    if only_deals:
        view = view[view["discount_pct"] >= 1]
    by = {"Price: low to high": ("sale_price", True), "Price: high to low": ("sale_price", False),
          "Discount": ("discount_pct", False), "Rating": ("rating", False)}.get(sort)
    if by:
        view = view.sort_values(by[0], ascending=by[1], na_position="last")

    head_l, head_r = st.columns([4, 1])
    head_l.markdown(f"<div class='sec'>{html.escape(title)} <span class='muted'>· {len(view):,} items</span></div>",
                    unsafe_allow_html=True)
    if ss.ai_ids and head_r.button("✕ Clear", use_container_width=True):
        ss.ai_ids = None
        st.rerun()

    pages = max(1, -(-len(view) // PAGE_SIZE))
    ss.page = min(ss.page, pages - 1)
    page_rows = view.iloc[ss.page * PAGE_SIZE:(ss.page + 1) * PAGE_SIZE].to_dict("records")
    if not page_rows:
        st.info("No products match these filters.")
    for row_start in range(0, len(page_rows), 4):
        cols = st.columns(4)
        for col, r in zip(cols, page_rows[row_start:row_start + 4]):
            col.markdown(product_card(r), unsafe_allow_html=True)
            if col.button("View details", key=f"d-{r['product_id']}", use_container_width=True):
                show_product(r["product_id"])

    if pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("← Previous", disabled=ss.page == 0, use_container_width=True):
            ss.page -= 1
            st.rerun()
        p2.markdown(f"<div class='muted' style='text-align:center;padding-top:8px'>Page {ss.page + 1} of {pages:,}</div>",
                    unsafe_allow_html=True)
        if p3.button("Next →", disabled=ss.page >= pages - 1, use_container_width=True):
            ss.page += 1
            st.rerun()

# =========================================================================== assistant column
EXAMPLES = [
    "Which is cheaper: Maggi noodles or Yippee noodles?",
    "Suggest a gluten-free snack under ₹150 and tell me its brand and rating",
    "What is the cheapest basmati rice?",
    "Compare Tata Tea and Red Label tea on price and rating",
    "Do you deliver to Pune within 10 minutes?",
]


def render_details(s: dict):
    with st.expander("🔍 Retrieval details"):
        st.markdown(f"**Best similarity:** {s['best']:.2f} (threshold {config.RELEVANCE_THRESHOLD}) · "
                    f"**Mode:** {s['mode']} · **Chunks:** {len(s['docs'])} · **Time:** {s['seconds']:.1f}s")
        if s.get("sub_queries"):
            st.markdown("**Query decomposition:** " + " · ".join(f"`{x}`" for x in s["sub_queries"]))
        if s.get("filter") and s["filter"] != [None, None]:
            lo, hi = s["filter"]
            st.markdown(f"**Price filter:** ₹{lo or 0} – {('₹' + str(hi)) if hi else 'any'}")
        if s.get("sort"):
            f, desc = s["sort"]
            st.markdown(f"**Sorted by:** {f.replace('_', ' ')} ({'high → low' if desc else 'low → high'})")
        if s.get("model"):
            st.markdown(f"**Answered by:** `{s['model']}`")
        if s.get("fallback"):
            st.markdown("**Guardrail:** similarity below threshold, so the LLM was not called.")
        for d in s["docs"]:
            st.caption(d["text"][:400] + ("…" if len(d["text"]) > 400 else ""))


def render_answer(content: str, s: dict | None, idx: int):
    if s and s.get("fallback"):
        st.markdown(f"<div class='fallback'>{html.escape(content)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(content)
    if not s:
        return
    if s["docs"] and not s.get("fallback"):
        with st.expander(f"🛒 Products used ({len(s['docs'])})", expanded=True):
            st.markdown("".join(mini_card(d["meta"]) for d in s["docs"]), unsafe_allow_html=True)
            if st.button("Show these in the store", key=f"show-{idx}", use_container_width=True):
                ss.ai_ids = [d["meta"]["product_id"] for d in s["docs"]]
                ss.page = 0
                st.rerun()
    render_details(s)


with assistant:
    st.markdown(f"<div class='assist-head'>{img_tag(image_path('🤖'), '🤖', 30)} Ask BasketBuddy</div>"
                "<div class='muted'>Answers come only from the catalogue. If it isn't there, I'll say so.</div>",
                unsafe_allow_html=True)
    box = st.container(height=640, border=True)
    with box:
        for i, msg in enumerate(ss.messages):
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🧺"):
                if msg["role"] == "user":
                    st.markdown(msg["content"])
                else:
                    render_answer(msg["content"], msg.get("sources"), i)
        if not ss.messages:
            st.markdown("**Try asking:**")
            for ex in EXAMPLES:
                if st.button(ex, key=f"ex-{ex}", use_container_width=True):
                    ss.pending = ex
                    st.rerun()

    question = st.chat_input("Ask about products, prices, comparisons…")
    if ss.get("pending"):
        question = ss.pop("pending")

    if question:
        ss.messages.append({"role": "user", "content": question})
        with box:
            with st.chat_message("user", avatar="🧑"):
                st.markdown(question)
            with st.chat_message("assistant", avatar="🧺"):
                with st.spinner("Searching the catalogue…"):
                    res = rag.answer(question, mode=mode, k=k)
                sources = {
                    "docs": [{"meta": d.metadata, "text": d.page_content} for d in res.docs],
                    "best": res.best_score, "filter": list(res.price_filter), "model": res.model,
                    "mode": mode, "fallback": res.used_fallback, "sub_queries": res.sub_queries,
                    "sort": res.sort, "seconds": res.seconds,
                }
                render_answer(res.answer, sources, len(ss.messages))
        ss.messages.append({"role": "assistant", "content": res.answer, "sources": sources})

st.markdown(
    "<div class='foot'>BasketBuddy is a student RAG project built on the public Kaggle dataset "
    "<i>BigBasket Entire Product List</i> (CC BY-NC-SA 4.0). Not affiliated with or endorsed by BigBasket. "
    "Prices are a dataset snapshot. Illustrations: Microsoft Fluent Emoji (MIT).</div>",
    unsafe_allow_html=True,
)
