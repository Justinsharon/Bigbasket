// BasketBuddy storefront (Streamlit Custom Component v2).
// Browsing, filters and the cart run in the browser from static/catalog.json.
// Search and the AI assistant call Python (hybrid RAG) through trigger values.

const IMG = "app/static/emoji/";
const CATALOG = "app/static/catalog.json";
const PHOTOS = "app/static/photos.json";
const FREE_DELIVERY = 199, DELIVERY_FEE = 25, HANDLING = 4;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + (Math.round(n * 100) / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 });

// Safe mini-markdown: escape first, then add a few formats (bold, italics, code, lists, tables, headings).
function md(src) {
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  const lines = String(src || "").split(/\r?\n/);
  let out = "", list = null, i = 0;
  const closeList = () => { if (list) { out += `</${list}>`; list = null; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^\s*\|.*\|\s*$/.test(l)) {
      closeList();
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = rows.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
      out += "<table>" + body.map((r, k) => "<tr>" + cells(r).map((c) =>
        k === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</table>";
      continue;
    }
    let m;
    if ((m = l.match(/^\s*#{1,6}\s+(.*)/))) { closeList(); out += `<h4>${inline(m[1])}</h4>`; }
    else if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { closeList(); out += "<ul>"; list = "ul"; } out += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { closeList(); out += "<ol>"; list = "ol"; } out += `<li>${inline(m[1])}</li>`; }
    else if (/^\s*(---|\*\*\*)\s*$/.test(l)) { closeList(); }
    else if (l.trim() === "") { closeList(); }
    else { closeList(); out += `<p>${inline(l)}</p>`; }
    i++;
  }
  closeList();
  return out;
}

function storeLoad() { try { return JSON.parse(localStorage.getItem("bb-cart") || "{}"); } catch { return {}; } }
function storeSave(c) { try { localStorage.setItem("bb-cart", JSON.stringify(c)); } catch { /* private mode */ } }

const SUGGESTED = [
  "Which is cheaper: Maggi noodles or Yippee noodles?",
  "Suggest a gluten-free snack under ₹150 and tell me its brand and rating",
  "What is the cheapest basmati rice?",
  "Compare Tata Tea and Red Label tea on price and rating",
  "Best rated green tea",
  "Do you deliver to Pune within 10 minutes?",
];

function createApp(root) {
  const S = {
    P: [], byId: new Map(), cats: {}, catImg: {}, ready: false,
    cart: storeLoad(), view: { name: "home" }, listLimit: 40,
    filters: { sort: "pop", r4: false, deal: false, u100: false },
    photos: {}, search: null, searchSent: null, chat: [], chatSent: null, pendingQ: null,
    details: {}, detailsSent: new Set(), trigger: null, mode: "hybrid", data: {},
  };

  // Load the brand font into the document (shadow roots inherit document fonts).
  if (!document.getElementById("bb-font")) {
    const l = document.createElement("link");
    l.id = "bb-font"; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap";
    document.head.appendChild(l);
  }

  const el = document.createElement("div");
  el.className = "bb";
  el.innerHTML = `
  <header class="hdr"><div class="hdr-in">
    <button class="logo" data-a="home"><img src="${IMG}1f9fa.webp" alt=""><span>Basket<b>Buddy</b></span></button>
    <div class="eta"><strong>Delivery in 10 minutes</strong><span>Bengaluru 560001 · demo</span></div>
    <div class="search"><form id="sf" autocomplete="off"><span class="ico">🔍</span>
      <input id="sq" placeholder="Search for “atta”, “shampoo”, “healthy snacks under ₹100”…" aria-label="Search products"></form>
      <div class="suggest" id="sg"></div></div>
    <button class="hbtn ai" data-a="ai"><img src="${IMG}1f916.webp" alt=""><span>Ask AI</span></button>
    <button class="hbtn cart" data-a="cart" id="cartBtn"></button>
  </div>
  <nav class="cats"><div class="cats-in" id="catbar"></div></nav></header>
  <main class="main" id="view"><div class="loading"><img src="${IMG}1f9fa.webp" alt="">Loading the store…</div></main>
  <footer class="foot"><div class="foot-in">
    <div><b>BasketBuddy</b> · demo quick-commerce store with a RAG shopping assistant.<br>
      Catalogue: Kaggle “BigBasket Entire Product List” (CC BY-NC-SA 4.0), a dataset snapshot.
      Not affiliated with or endorsed by BigBasket. No real orders or payments.</div>
    <div>Photos: <a href="https://unsplash.com/?utm_source=basketbuddy_student_rag&utm_medium=referral" target="_blank" rel="noopener">Unsplash</a> photographers (<button data-a="credits">credits</button>) · Illustrations: Microsoft Fluent Emoji (MIT)<br>
      <button data-a="classic">Open the classic Streamlit chat →</button></div>
  </div></footer>
  <button class="fab" data-a="ai"><img src="${IMG}1f916.webp" alt=""><span>Ask BasketBuddy AI</span></button>
  <div class="scrim" id="scrim" data-a="close"></div>
  <aside class="drawer" id="cartDr" aria-label="Basket">
    <div class="dr-h"><h3>My basket<small id="cartSub"></small></h3><button class="x" data-a="close">✕</button></div>
    <div class="dr-b" id="cartBody"></div><div class="dr-f" id="cartFoot"></div></aside>
  <aside class="drawer ai-drawer" id="aiDr" aria-label="AI assistant">
    <div class="dr-h"><img src="${IMG}1f916.webp" alt=""><h3>BasketBuddy AI
      <small>Answers only from the product catalogue · says so when it doesn't know</small></h3>
      <button class="x" data-a="close">✕</button></div>
    <div class="dr-b" id="chatBody"></div>
    <div class="dr-f"><form class="chat-in" id="cf" autocomplete="off">
      <input id="cq" placeholder="Ask about products, prices, comparisons…" aria-label="Ask the assistant">
      <button class="send" aria-label="Send">➤</button></form>
      <div class="chat-opts"><label>Retrieval <select id="mode"><option value="hybrid">Hybrid (BM25 + vector)</option>
        <option value="vector">Vector only</option></select></label><button data-a="clearchat">Clear chat</button></div>
    </div></aside>
  <div class="modal" id="modal"><div class="scrim on" data-a="close"></div><div class="card" id="pd"></div></div>
  <div class="toast" id="toast"></div>`;
  root.appendChild(el);
  const $ = (id) => root.getElementById ? root.getElementById(id) : el.querySelector("#" + id);

  // ------------------------------------------------------------------ helpers
  const img = (p) => IMG + (p.img || "1f6d2.webp");
  // Real photo (Unsplash, hotlinked) for the product's image concept, if one was picked.
  const photo = (p) => S.photos[(p.img || "").replace(".webp", "").replace("-fe0f", "")];
  const pimg = (p, lazy = true) => { const ph = photo(p); return ph
    ? `<img class="photo" ${lazy ? 'loading="lazy"' : ""} src="${esc(ph.url)}" alt="${esc(ph.alt)}">`
    : `<img ${lazy ? 'loading="lazy"' : ""} src="${img(p)}" alt="">`; };
  const qty = (id) => S.cart[id] || 0;
  function toast(t) { const n = $("toast"); n.textContent = t; n.classList.add("on");
    clearTimeout(S._t); S._t = setTimeout(() => n.classList.remove("on"), 1600); }
  function scrollTop() {
    const sc = document.querySelector('[data-testid="stMain"]') || document.querySelector(".main");
    try { sc && sc.scrollTo({ top: 0 }); window.scrollTo({ top: 0 }); } catch { /* ignore */ }
  }
  function addBtn(p) {
    const q = qty(p.id);
    return q ? `<div class="step"><button data-a="dec" data-id="${p.id}" aria-label="Remove one">−</button><span>${q}</span>
      <button data-a="inc" data-id="${p.id}" aria-label="Add one">+</button></div>`
      : `<button class="add" data-a="inc" data-id="${p.id}">ADD</button>`;
  }
  function card(p) {
    const rib = p.off >= 1 ? `<span class="ribbon">${p.off}%<br>OFF</span>` : "";
    const rt = p.rating ? `<span class="rt">★ ${p.rating.toFixed(1)}</span>` : "";
    return `<div class="pc" data-pid="${p.id}">
      <div class="pc-img" data-a="open" data-id="${p.id}">${rib}${pimg(p)}</div>
      <span class="pc-eta">⚡ 10 MINS</span>
      <div class="pc-brand">${esc(p.brand)}</div>
      <div class="pc-name" data-a="open" data-id="${p.id}" title="${esc(p.name)}">${esc(p.name)}</div>
      <div class="pc-sub">${rt}<span class="pc-type">${esc(p.type)}</span></div>
      <div class="pc-foot"><div class="price"><b>${inr(p.price)}</b>${p.mrp > p.price ? `<s>${inr(p.mrp)}</s>` : ""}</div>
        <span class="addslot" data-id="${p.id}">${addBtn(p)}</span></div></div>`;
  }
  const grid = (list) => `<div class="grid">${list.map(card).join("")}</div>`;
  function rail(title, list, action) {
    const id = "r" + Math.random().toString(36).slice(2, 8);
    return `<section class="sec"><div class="sec-h"><h2>${esc(title)}</h2>
      ${action ? `<button data-a="${action.a}" data-v="${esc(action.v || "")}">See all ›</button>` : ""}</div>
      <div class="rail-wrap"><button class="rail-btn l" data-a="rail" data-r="${id}" data-d="-1">‹</button>
      <div class="rail" id="${id}">${list.map(card).join("")}</div>
      <button class="rail-btn r" data-a="rail" data-r="${id}" data-d="1">›</button></div></section>`;
  }
  function refreshAddSlots() {
    el.querySelectorAll(".addslot").forEach((s) => { const p = S.byId.get(+s.dataset.id); if (p) s.innerHTML = addBtn(p); });
    const pdSlot = $("pd").querySelector(".pd-add");
    if (pdSlot) { const p = S.byId.get(+pdSlot.dataset.id); pdSlot.innerHTML = addBtn(p); }
  }

  // ------------------------------------------------------------------ cart
  function cartTotals() {
    let items = 0, total = 0, mrp = 0;
    for (const [id, q] of Object.entries(S.cart)) { const p = S.byId.get(+id); if (!p) continue;
      items += q; total += p.price * q; mrp += Math.max(p.mrp, p.price) * q; }
    const delivery = items && total < FREE_DELIVERY ? DELIVERY_FEE : 0;
    return { items, total, mrp, delivery, handling: items ? HANDLING : 0, grand: total + delivery + (items ? HANDLING : 0) };
  }
  function setQty(id, q) {
    if (q <= 0) delete S.cart[id]; else S.cart[id] = q;
    storeSave(S.cart); renderCartBtn(); refreshAddSlots();
    if ($("cartDr").classList.contains("on")) renderCart();
    if (S.view.name === "checkout") render();
  }
  function renderCartBtn() {
    const t = cartTotals();
    $("cartBtn").innerHTML = t.items
      ? `<img src="${IMG}1f6d2.webp" alt=""><span class="l"><b>${t.items} item${t.items > 1 ? "s" : ""}</b>${inr(t.total)}</span><i class="cnt">${t.items}</i>`
      : `<img src="${IMG}1f6d2.webp" alt=""><span class="txt">My Basket</span>`;
  }
  function billHtml(t) {
    return `<div class="bill"><div><span>Items total (MRP)</span><span>${inr(t.mrp)}</span></div>
      <div class="save"><span>Product discount</span><span>−${inr(t.mrp - t.total)}</span></div>
      <div><span>Delivery fee</span><span>${t.delivery ? inr(t.delivery) : "<b style='color:#047857'>FREE</b>"}</span></div>
      <div><span>Handling charge</span><span>${inr(t.handling)}</span></div>
      <div class="tot"><span>To pay</span><span>${inr(t.grand)}</span></div></div>`;
  }
  function renderCart() {
    const t = cartTotals(), ids = Object.keys(S.cart);
    $("cartSub").textContent = t.items ? `${t.items} item${t.items > 1 ? "s" : ""} · you save ${inr(t.mrp - t.total)}` : "";
    if (!ids.length) {
      $("cartBody").innerHTML = `<div class="empty"><img src="${IMG}1f6d2.webp" alt=""><b>Your basket is empty</b>
        <p>Add items from the store, or ask BasketBuddy AI for ideas.</p></div>`;
      $("cartFoot").innerHTML = `<button class="cta" data-a="home" style="justify-content:center">Start shopping</button>`;
      return;
    }
    const gap = FREE_DELIVERY - t.total;
    $("cartBody").innerHTML = (gap > 0 ? `<div class="freebar">Add items worth ${inr(gap)} more for FREE delivery</div>`
      : `<div class="freebar" style="background:#ecfdf5;color:#047857">🎉 You've unlocked FREE delivery</div>`) +
      `<div class="box">${ids.map((id) => { const p = S.byId.get(+id); return !p ? "" : `<div class="ci">
        <div class="im">${pimg(p)}</div><div><div class="n">${esc(p.name)}</div>
        <div class="p"><b>${inr(p.price)}</b>${p.mrp > p.price ? `<s>${inr(p.mrp)}</s>` : ""}</div></div>
        <span class="addslot" data-id="${p.id}">${addBtn(p)}</span></div>`; }).join("")}</div>
      <div class="box"><b>Bill details</b>${billHtml(t)}</div>`;
    $("cartFoot").innerHTML = `<button class="cta" data-a="checkout"><span>${inr(t.grand)}<br><small style="font-weight:600;opacity:.85">TOTAL</small></span><span>Proceed to checkout ›</span></button>`;
  }

  // ------------------------------------------------------------------ views
  function catBar() {
    const active = S.view.name === "cat" ? S.view.cat : S.view.name === "home" ? "__home" : "";
    $("catbar").innerHTML = `<button data-a="home" class="${active === "__home" ? "on" : ""}">Home</button>` +
      Object.keys(S.cats).map((c) => `<button data-a="cat" data-v="${esc(c)}" class="${active === c ? "on" : ""}">${esc(c)}</button>`).join("");
  }
  function homeView() {
    const P = S.P, by = (f, s, n) => P.filter(f).sort(s).slice(0, n);
    const deals = by((p) => p.off >= 25 && p.rating >= 4, (a, b) => b.off - a.off, 20);
    const fresh = by((p) => p.cat === "Fruits & Vegetables", (a, b) => (b.rating || 0) - (a.rating || 0) || b.off - a.off, 20);
    const dairy = by((p) => p.cat === "Bakery, Cakes & Dairy" && p.rating, (a, b) => b.rating - a.rating, 20);
    const snacks = by((p) => p.cat === "Snacks & Branded Foods" && p.price <= 50 && p.rating >= 4, (a, b) => b.rating - a.rating, 20);
    const bev = by((p) => p.cat === "Beverages" && p.rating, (a, b) => b.rating - a.rating || b.off - a.off, 20);
    const beauty = by((p) => p.cat === "Beauty & Hygiene" && p.rating >= 4.2, (a, b) => b.off - a.off, 20);
    const maxFresh = Math.max(...P.filter((p) => p.cat === "Fruits & Vegetables").map((p) => p.off));
    const maxBeauty = Math.max(...P.filter((p) => p.cat === "Beauty & Hygiene").map((p) => p.off));
    const pastel = ["#e8f7ee", "#fff4e0", "#fde8ef", "#e8f0ff", "#fff8d6", "#efe9ff", "#e5f6f8", "#fdeee6", "#eef7e2", "#f2f2f2", "#e9f5ef"];
    return `
    <section class="banners">
      <button class="banner b1" data-a="cat" data-v="Fruits & Vegetables"><div><h3>Fresh fruits & vegetables</h3>
        <p>${S.cats["Fruits & Vegetables"]} fresh picks, up to ${maxFresh}% off</p></div>
        <span class="bcta">Shop fresh</span><img src="${IMG}1f966.webp" alt=""></button>
      <button class="banner b2" data-a="deals" data-v="Beauty & Hygiene"><div><h3>Beauty & personal care sale</h3>
        <p>Top brands with up to ${maxBeauty}% off</p></div><span class="bcta">Grab deals</span>
        <img src="${IMG}1f9f4.webp" alt=""></button>
      <button class="banner b3" data-a="ai"><div><h3>Not sure what to buy?</h3>
        <p>Ask BasketBuddy AI to compare brands, find deals or match a budget</p></div>
        <span class="bcta">Ask AI ✨</span><img src="${IMG}1f916.webp" alt=""></button>
    </section>
    <section class="sec"><div class="sec-h"><h2>Shop by category</h2></div><div class="tiles">
      ${Object.keys(S.cats).map((c, i) => `<button class="tile" data-a="cat" data-v="${esc(c)}">
        <div class="ib" style="background:${pastel[i % pastel.length]}"><img src="${IMG}${S.catImg[c]}" alt=""></div>
        <span>${esc(c)}</span></button>`).join("")}</div></section>
    ${rail("Today's top deals", deals, { a: "deals", v: "" })}
    ${rail("Fresh fruits & vegetables", fresh, { a: "cat", v: "Fruits & Vegetables" })}
    <section class="sec"><div class="ai-strip"><img src="${IMG}1f916.webp" alt=""><div>
      <h3>Shop smarter with BasketBuddy AI</h3>
      <p>Grounded answers from ${S.P.length.toLocaleString("en-IN")} products. It compares brands, filters by budget, and tells you when something isn't in the catalogue.</p>
      <div class="qchips">${SUGGESTED.slice(0, 4).map((q) => `<button class="qchip" data-a="ask" data-v="${esc(q)}">${esc(q)}</button>`).join("")}</div>
    </div></div></section>
    ${rail("Dairy & bakery bestsellers", dairy, { a: "cat", v: "Bakery, Cakes & Dairy" })}
    ${rail("Snacks under ₹50", snacks, { a: "cat", v: "Snacks & Branded Foods" })}
    ${rail("Beverages", bev, { a: "cat", v: "Beverages" })}
    ${rail("Beauty favourites on offer", beauty, { a: "deals", v: "Beauty & Hygiene" })}`;
  }
  function applyFilters(list, keepOrder) {
    const f = S.filters;
    let out = list.filter((p) => (!f.r4 || p.rating >= 4) && (!f.deal || p.off >= 1) && (!f.u100 || p.price <= 100));
    const sorts = {
      pop: (a, b) => (b.rating || 0) - (a.rating || 0) || b.off - a.off,
      low: (a, b) => a.price - b.price, high: (a, b) => b.price - a.price,
      off: (a, b) => b.off - a.off, rating: (a, b) => (b.rating || 0) - (a.rating || 0),
    };
    if (!(keepOrder && f.sort === "pop")) out = out.slice().sort(sorts[f.sort]);
    return out;
  }
  function toolbar(title, count, relevanceLabel) {
    const f = S.filters;
    return `<div class="toolbar"><h1>${title} <small>${count.toLocaleString("en-IN")} items</small></h1>
      <button class="chip ${f.deal ? "on" : ""}" data-a="flt" data-v="deal">On offer</button>
      <button class="chip ${f.r4 ? "on" : ""}" data-a="flt" data-v="r4">Rated 4★ +</button>
      <button class="chip ${f.u100 ? "on" : ""}" data-a="flt" data-v="u100">Under ₹100</button>
      <select class="sel" id="sortSel" aria-label="Sort">
        ${[["pop", relevanceLabel || "Popular"], ["low", "Price: low to high"], ["high", "Price: high to low"], ["off", "Biggest discount"], ["rating", "Top rated"]]
          .map(([v, t]) => `<option value="${v}" ${f.sort === v ? "selected" : ""}>Sort: ${t}</option>`).join("")}
      </select></div>`;
  }
  function listView() {
    const v = S.view;
    let base = S.P, title, crumbs = `<button data-a="home">Home</button>`, side = "";
    if (v.name === "cat") {
      base = S.P.filter((p) => p.cat === v.cat);
      const subs = {}; base.forEach((p) => { subs[p.sub] = (subs[p.sub] || 0) + 1; });
      side = `<aside class="side"><button class="${!v.sub ? "on" : ""}" data-a="sub" data-v="">All <small>${base.length}</small></button>
        ${Object.entries(subs).sort((a, b) => b[1] - a[1]).map(([s, n]) => `<button class="${v.sub === s ? "on" : ""}" data-a="sub" data-v="${esc(s)}">${esc(s)} <small>${n}</small></button>`).join("")}</aside>`;
      if (v.sub) base = base.filter((p) => p.sub === v.sub);
      title = esc(v.sub || v.cat); crumbs += ` › <button data-a="cat" data-v="${esc(v.cat)}">${esc(v.cat)}</button>${v.sub ? " › " + esc(v.sub) : ""}`;
    } else if (v.name === "deals") {
      base = S.P.filter((p) => p.off >= 1 && (!v.cat || p.cat === v.cat));
      if (S.filters.sort === "pop") base = base.slice().sort((a, b) => b.off - a.off);
      title = v.cat ? `Deals in ${esc(v.cat)}` : "All deals";
      crumbs += " › Deals";
    } else if (v.name === "ids") {
      base = v.ids.map((id) => S.byId.get(id)).filter(Boolean);
      title = esc(v.title); crumbs += " › Assistant picks";
    }
    const list = applyFilters(base, v.name !== "cat");
    const body = list.length ? grid(list.slice(0, S.listLimit)) +
      (list.length > S.listLimit ? `<button class="more" data-a="more">Show more (${(list.length - S.listLimit).toLocaleString("en-IN")} left)</button>` : "")
      : `<div class="empty"><img src="${IMG}1f50d.webp" alt=""><b>No products match these filters</b></div>`;
    const content = `<div class="crumbs">${crumbs}</div>${toolbar(title, list.length)}${body}`;
    return side ? `<div class="listing">${side}<div>${content}</div></div>` : content;
  }
  function searchView() {
    const q = S.view.q, res = S.search && S.search.q === q ? S.search : null;
    const hint = `<div class="ai-hint"><img src="${IMG}1f916.webp" alt=""><div><b>Want advice instead of a list?</b>
      Ask BasketBuddy AI about “${esc(q)}”. It answers from the catalogue only.</div>
      <button data-a="ask" data-v="${esc(q)}">Ask AI</button></div>`;
    if (!res) return `<div class="crumbs"><button data-a="home">Home</button> › Search</div>
      <div class="toolbar"><h1>Searching for “${esc(q)}”…</h1></div><div class="grid">${"<div class='sk'></div>".repeat(10)}</div>`;
    const list = applyFilters(res.ids.map((id) => S.byId.get(id)).filter(Boolean), true);
    return `<div class="crumbs"><button data-a="home">Home</button> › Search</div>${hint}
      ${toolbar(`Results for “${esc(q)}”`, list.length, "Relevance")}
      <div class="tag-hybrid" style="margin:-6px 0 12px">Ranked by hybrid search: BM25 keywords + FAISS semantic vectors, fused with RRF.</div>
      ${list.length ? grid(list) : `<div class="empty"><img src="${IMG}1f50d.webp" alt=""><b>No products found</b><p>Try another word, or ask the AI.</p></div>`}`;
  }
  function checkoutView() {
    if (S.view.done) return `<div class="done"><img src="${IMG}1f6f5.webp" alt="" onerror="this.src='${IMG}1f389.webp'">
      <h1>Order placed! 🎉</h1><p>Order <b>#${S.view.done}</b> is being packed and will arrive in about 10 minutes.</p>
      <p class="demo-note">This is a demo store. No real order was placed and nothing was charged.</p>
      <button class="cta" data-a="home" style="max-width:260px;margin:14px auto 0;justify-content:center">Continue shopping</button></div>`;
    const t = cartTotals();
    if (!t.items) return `<div class="empty"><img src="${IMG}1f6d2.webp" alt=""><b>Your basket is empty</b><br><br>
      <button class="more" data-a="home">Start shopping</button></div>`;
    return `<div class="co"><div><h1>Checkout</h1>
      <div class="box"><h3>Delivery address</h3><div class="opt on">🏠 <div><b>Home</b><br><span style="color:#6b7280">12, 4th Cross, Indiranagar, Bengaluru 560001 (demo)</span></div></div></div>
      <div class="box"><h3>Delivery slot</h3><div class="opt on">⚡ <b>Express: in 10 minutes</b></div></div>
      <div class="box"><h3>Payment</h3><div class="opt on">💵 <b>Cash / UPI on delivery</b></div>
        <p class="demo-note">Demo checkout: no payment details are collected.</p></div></div>
      <div><div class="box"><b>Order summary · ${t.items} items</b>${billHtml(t)}</div>
      <button class="cta" data-a="place"><span>${inr(t.grand)}</span><span>Place order ›</span></button></div></div>`;
  }
  function render() {
    if (!S.ready) return;
    catBar();
    const v = S.view.name;
    $("view").innerHTML = v === "home" ? homeView() : v === "search" ? searchView() : v === "checkout" ? checkoutView() : listView();
    const sel = $("view").querySelector("#sortSel");
    if (sel) sel.onchange = () => { S.filters.sort = sel.value; S.listLimit = 40; render(); };
  }
  function go(view) { S.view = view; S.listLimit = 40; closeAll(); render(); scrollTop(); }

  // ------------------------------------------------------------------ product modal
  function openProduct(id) {
    const p = S.byId.get(id); if (!p) return;
    const d = S.details[id];
    if (!d && !S.detailsSent.has(id)) { S.detailsSent.add(id); S.trigger("details", id); }
    $("pd").innerHTML = `<button class="x" data-a="close">✕</button>
      <div class="pd-img">${p.off >= 1 ? `<span class="ribbon" style="left:16px">${p.off}%<br>OFF</span>` : ""}${pimg(p, false)}</div>
      <div class="pd"><div class="crumbs">${esc(p.cat)} › ${esc(p.sub)} › ${esc(p.type)}</div>
        <h2>${esc(p.name)}</h2><span class="br">${esc(p.brand)}</span>
        ${p.rating ? ` · <span class="rt">★ ${p.rating.toFixed(1)}</span>` : ` · <span style="color:#6b7280;font-size:12px">Not rated</span>`}
        <div class="prow"><b>${inr(p.price)}</b>${p.mrp > p.price ? `<s>MRP ${inr(p.mrp)}</s><span class="off">${p.off}% OFF</span>` : ""}</div>
        <div class="tax">Inclusive of all taxes · ⚡ Delivery in 10 minutes</div>
        <div class="act"><span class="pd-add" data-id="${p.id}">${addBtn(p)}</span>
          <button class="ask" data-a="ask" data-v="${esc(`Tell me about ${p.name} by ${p.brand}: what is it, its price and rating?`)}">✨ Ask AI about this</button></div>
        <h4>Product details</h4><div class="desc" id="pdDesc">${d ? esc(d) : "Loading description…"}</div>
        <h4>Information</h4><div class="facts"><span>Brand</span><span>${esc(p.brand)}</span><span>Category</span><span>${esc(p.cat)}</span>
          <span>Type</span><span>${esc(p.type)}</span><span>Source</span><span>Kaggle BigBasket dataset</span></div>
        ${photo(p) ? `<p class="credit">Illustrative photo of the product type (not the exact item) by
          <a href="${esc(photo(p).author_url)}" target="_blank" rel="noopener">${esc(photo(p).author)}</a> on
          <a href="${esc(photo(p).unsplash_url)}" target="_blank" rel="noopener">Unsplash</a></p>` : ""}</div>`;
    $("modal").classList.add("on"); S.openPid = id;
  }

  // ------------------------------------------------------------------ chat
  function renderChat() {
    const body = $("chatBody");
    let h = "";
    if (!S.chat.length && !S.pendingQ) {
      h = `<div class="welcome"><img src="${IMG}1f916.webp" alt=""><h4>Hi! I'm BasketBuddy AI</h4>
        <p>I search ${S.P.length.toLocaleString("en-IN")} catalogue products and answer only from what I find.</p>
        <div class="qchips">${SUGGESTED.map((q) => `<button class="qchip" data-a="ask" data-v="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>`;
    }
    S.chat.forEach((m, i) => {
      if (m.role === "user") { h += `<div class="msg u"><div class="bub">${esc(m.content)}</div></div>`; return; }
      const meta = m.meta || {}, prods = (m.ids || []).map((id) => S.byId.get(id)).filter(Boolean);
      const minis = !meta.fallback && prods.length ? `<div class="minis">${prods.map((p) => `<div class="mini">
          <div class="im" data-a="open" data-id="${p.id}">${pimg(p)}</div><div class="n">${esc(p.name)}</div>
          <div class="pr">${inr(p.price)}<span class="addslot" data-id="${p.id}">${addBtn(p)}</span></div></div>`).join("")}</div>
          <div class="links"><button data-a="showids" data-i="${i}">View these ${prods.length} in the store ›</button></div>` : "";
      const kv = [["Best similarity", `${(meta.best || 0).toFixed(2)} (threshold ${meta.threshold})`], ["Retrieval", meta.mode],
        ["Chunks used", String((m.ids || []).length)], ["Time", `${(meta.seconds || 0).toFixed(1)} s`]];
      if (meta.sub_queries && meta.sub_queries.length) kv.push(["Decomposition", meta.sub_queries.join(" · ")]);
      if (meta.filter && (meta.filter[0] != null || meta.filter[1] != null)) kv.push(["Price filter", `₹${meta.filter[0] || 0} – ${meta.filter[1] != null ? "₹" + meta.filter[1] : "any"}`]);
      if (meta.sort) kv.push(["Sorted by", `${meta.sort[0].replace("_", " ")} (${meta.sort[1] ? "high → low" : "low → high"})`]);
      if (meta.model) kv.push(["Model", meta.model]);
      if (meta.fallback) kv.push(["Guardrail", "Below threshold, so the LLM was not called"]);
      h += `<div class="msg a"><div class="bub ${meta.fallback ? "fb" : ""}">${md(m.content)}${minis}
        <details class="rd"><summary>How I found this</summary><div class="kv">${kv.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join("")}</div></details>
        </div></div>`;
    });
    if (S.pendingQ) h += `<div class="msg u"><div class="bub">${esc(S.pendingQ)}</div></div>
      <div><span class="typing"><i></i><i></i><i></i></span><div class="typing-l">Searching the catalogue and writing a grounded answer…</div></div>`;
    body.innerHTML = h;
    body.scrollTop = body.scrollHeight;
  }
  function ask(q) {
    q = (q || "").trim(); if (!q || S.pendingQ) return;
    openDrawer("aiDr"); S.pendingQ = q; renderChat();
    S.chatSent = { q, n: S.chat.length };
    S.trigger("ask", { q, mode: $("mode").value, nonce: Date.now() });
  }

  // ------------------------------------------------------------------ drawers
  function openDrawer(id) {
    $("modal").classList.remove("on");
    ["cartDr", "aiDr"].forEach((d) => $(d).classList.toggle("on", d === id));
    $("scrim").classList.add("on");
    if (id === "cartDr") renderCart(); else { renderChat(); setTimeout(() => $("cq").focus(), 250); }
  }
  function closeAll() {
    ["cartDr", "aiDr"].forEach((d) => $(d).classList.remove("on"));
    $("scrim").classList.remove("on"); $("modal").classList.remove("on"); S.openPid = null;
  }

  // ------------------------------------------------------------------ search box + suggestions
  const sq = $("sq"), sg = $("sg");
  let hl = -1;
  function suggest() {
    const q = sq.value.trim().toLowerCase();
    if (q.length < 2 || !S.ready) { sg.classList.remove("on"); return; }
    const words = q.split(/\s+/);
    const hits = []; for (const p of S.P) { const s = (p.name + " " + p.brand).toLowerCase();
      if (words.every((w) => s.includes(w))) { hits.push(p); if (hits.length >= 6) break; } }
    sg.innerHTML = hits.map((p, i) => `<button data-a="open" data-id="${p.id}" class="${i === hl ? "hl" : ""}">
        ${pimg(p)}<span>${esc(p.name)}<small>${esc(p.brand)} · ${inr(p.price)}</small></span></button>`).join("") +
      `<button class="ai" data-a="ask" data-v="${esc(sq.value.trim())}">✨ Ask AI about “${esc(sq.value.trim())}”</button>`;
    sg.classList.add("on");
  }
  sq.addEventListener("input", () => { hl = -1; suggest(); });
  sq.addEventListener("focus", suggest);
  sq.addEventListener("blur", () => setTimeout(() => sg.classList.remove("on"), 180));
  $("sf").addEventListener("submit", (e) => {
    e.preventDefault(); const q = sq.value.trim(); if (!q) return;
    sg.classList.remove("on"); sq.blur();
    go({ name: "search", q });
    if (!(S.search && S.search.q === q)) { S.searchSent = q; S.trigger("search", { q, nonce: Date.now() }); }
  });
  $("cf").addEventListener("submit", (e) => { e.preventDefault(); const v = $("cq").value; $("cq").value = ""; ask(v); });
  root.addEventListener && root.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAll(); });

  // ------------------------------------------------------------------ click delegation
  el.addEventListener("click", (e) => {
    const t = e.target.closest("[data-a]"); if (!t) return;
    const a = t.dataset.a, v = t.dataset.v, id = t.dataset.id != null ? +t.dataset.id : null;
    switch (a) {
      case "home": go({ name: "home" }); break;
      case "cat": S.filters = { sort: "pop", r4: false, deal: false, u100: false }; go({ name: "cat", cat: v }); break;
      case "sub": S.view = { ...S.view, sub: v || null }; S.listLimit = 40; render(); scrollTop(); break;
      case "deals": S.filters = { sort: "pop", r4: false, deal: false, u100: false }; go({ name: "deals", cat: v || null }); break;
      case "flt": S.filters[v] = !S.filters[v]; S.listLimit = 40; render(); break;
      case "more": S.listLimit += 40; render(); break;
      case "inc": { const was = qty(id); setQty(id, was + 1); if (!was) toast("Added to basket"); break; }
      case "dec": setQty(id, qty(id) - 1); break;
      case "open": sg.classList.remove("on"); openProduct(id); break;
      case "cart": openDrawer("cartDr"); break;
      case "ai": openDrawer("aiDr"); break;
      case "ask": sg.classList.remove("on"); $("modal").classList.remove("on"); ask(v); break;
      case "close": closeAll(); break;
      case "clearchat": S.trigger("clearchat", Date.now()); S.chat = []; renderChat(); break;
      case "showids": { const m = S.chat[+t.dataset.i]; go({ name: "ids", ids: m.ids, title: "Products from the assistant's answer" }); break; }
      case "rail": { const r = el.querySelector("#" + t.dataset.r); r && r.scrollBy({ left: +t.dataset.d * r.clientWidth * 0.8 }); break; }
      case "checkout": go({ name: "checkout" }); break;
      case "place": { const no = "BB" + Math.floor(100000 + Math.random() * 900000); S.cart = {}; storeSave(S.cart);
        renderCartBtn(); S.view = { name: "checkout", done: no }; render(); scrollTop(); break; }
      case "classic": S.trigger("nav", "classic"); break;
      case "credits": {
        const used = Object.values(S.photos);
        $("pd").innerHTML = `<button class="x" data-a="close">✕</button><div class="pd" style="grid-column:1/-1">
          <h2>Photo credits</h2><p class="credit">Product photos are illustrative photos of each product type, hotlinked from
          <a href="https://unsplash.com/?utm_source=basketbuddy_student_rag&utm_medium=referral" target="_blank" rel="noopener">Unsplash</a>.
          Products without a photo use Microsoft Fluent Emoji 3D illustrations (MIT).</p>
          <div class="credits">${used.map((c) => `<a href="${esc(c.photo_url)}" target="_blank" rel="noopener">
            <img src="${esc(c.url)}" alt="${esc(c.alt)}" loading="lazy"><span>${esc(c.query)}<small>by ${esc(c.author)}</small></span></a>`).join("")}</div></div>`;
        $("modal").classList.add("on"); break;
      }
    }
  });

  // ------------------------------------------------------------------ data from Python
  S.update = (data) => {
    S.data = data || {};
    if (S.data.search && (!S.search || S.data.search.nonce !== S.search.nonce)) {
      S.search = S.data.search;
      if (S.view.name === "search" && S.view.q === S.search.q) render();
    }
    if (Array.isArray(S.data.chat)) {
      const grew = S.data.chat.length !== S.chat.length;
      S.chat = S.data.chat;
      if (S.pendingQ && S.chatSent && S.chat.length > S.chatSent.n) S.pendingQ = null;
      if (grew || !S.pendingQ) renderChat();
    }
    if (S.data.details) {
      for (const [id, txt] of Object.entries(S.data.details)) S.details[id] = txt;
      if (S.openPid != null && S.details[S.openPid] != null) { const d = $("pdDesc"); if (d) d.textContent = S.details[S.openPid]; }
    }
  };

  // ------------------------------------------------------------------ boot
  fetch(CATALOG).then((r) => r.json()).then((j) => {
    const F = j.fields;
    S.P = j.rows.map((r) => Object.fromEntries(F.map((f, i) => [f, r[i]])));
    S.P.forEach((p) => { S.byId.set(p.id, p); S.cats[p.cat] = (S.cats[p.cat] || 0) + 1; });
    S.cats = Object.fromEntries(Object.entries(S.cats).sort((a, b) => b[1] - a[1]));
    S.catImg = j.cats || {};
    S.ready = true; renderCartBtn(); render(); S.update(S.data);
    // Optional real photos; the store works with illustrations if this file is missing.
    fetch(PHOTOS).then((r) => (r.ok ? r.json() : {})).then((ph) => { S.photos = ph || {}; render(); }).catch(() => {});
  }).catch(() => { $("view").innerHTML = `<div class="empty"><b>Couldn't load the catalogue.</b><p>Please refresh the page.</p></div>`; });

  return S;
}

export default function (component) {
  const { parentElement, data, setTriggerValue } = component;
  let S = parentElement.__bb;
  if (!S) S = parentElement.__bb = createApp(parentElement);
  S.trigger = setTriggerValue;
  S.update(data);
}
