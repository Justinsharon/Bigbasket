// BasketBuddy storefront v2 (Streamlit Custom Component v2).
// Browsing, wishlist, coupons and the basket run in the browser from static/catalog.json.
// Search and the AI assistant call Python (hybrid RAG) through trigger values.

const IMG = "app/static/emoji/";
const CATALOG = "app/static/catalog.json";
const PHOTOS = "app/static/photos.json";
const FREE_DELIVERY = 199, DELIVERY_FEE = 25, HANDLING = 4;
const UTM = "utm_source=basketbuddy_student_rag&utm_medium=referral";

// Demo coupons (no real discounts are issued: this is a demo store).
const COUPONS = {
  BUDDY5: { title: "5% off up to ₹50", sub: "On orders above ₹300", min: 300, calc: (t) => Math.min(50, t * 0.05), cls: "" },
  FRESH30: { title: "Flat ₹30 off", sub: "On orders above ₹499", min: 499, calc: () => 30, cls: "t2" },
  AIPICK: { title: "₹20 off AI picks", sub: "On orders above ₹150", min: 150, calc: () => 20, cls: "t3" },
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + (Math.round(n * 100) / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 });

// Small inline icons (simple original strokes).
const I = {
  search: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>`,
  heart: `<svg width="18" height="18" viewBox="0 0 24 24"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 7.8 3.6 4.5 7 4.5c2 0 3.4 1.1 5 3 1.6-1.9 3-3 5-3 3.4 0 5.6 3.3 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  pin: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>`,
  down: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg>`,
  back: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>`,
  trash: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>`,
  bolt: `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"/></svg>`,
  clock: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/></svg>`,
  send: `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3 20l18-8L3 4v6l12 2-12 2z"/></svg>`,
  x: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
};

// Safe mini-markdown: escape first, then add a few formats.
function md(src) {
  const inline = (t) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  const lines = String(src || "").split(/\r?\n/);
  let out = "", list = null, i = 0;
  const close = () => { if (list) { out += `</${list}>`; list = null; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^\s*\|.*\|\s*$/.test(l)) {
      close(); const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      out += "<table>" + rows.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r)).map((r, k) => "<tr>" +
        cells(r).map((c) => (k ? `<td>${inline(c)}</td>` : `<th>${inline(c)}</th>`)).join("") + "</tr>").join("") + "</table>";
      continue;
    }
    let m;
    if ((m = l.match(/^\s*#{1,6}\s+(.*)/))) { close(); out += `<h4>${inline(m[1])}</h4>`; }
    else if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { close(); out += "<ul>"; list = "ul"; } out += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { close(); out += "<ol>"; list = "ol"; } out += `<li>${inline(m[1])}</li>`; }
    else if (l.trim() === "" || /^\s*(---|\*\*\*)\s*$/.test(l)) close();
    else { close(); out += `<p>${inline(l)}</p>`; }
    i++;
  }
  close();
  return out;
}

const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } };

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
    P: [], byId: new Map(), cats: {}, catImg: {}, photos: {}, ready: false,
    cart: load("bb-cart", {}), wish: load("bb-wish", []), coupon: load("bb-coupon", null), mode: load("bb-mode", "instant"),
    view: { name: "home" }, listLimit: 40, lq: "", filters: { sort: "pop", r4: false, deal: false, u100: false },
    search: null, chat: [], chatSent: null, pendingQ: null, details: {}, detailsSent: new Set(), trigger: () => {}, data: {},
  };

  if (!document.getElementById("bb-font")) {
    const l = document.createElement("link");
    l.id = "bb-font"; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap";
    document.head.appendChild(l);
  }

  const el = document.createElement("div");
  el.className = "bb";
  el.innerHTML = `
  <header class="top"><div class="wrap">
    <button class="logo" data-a="home"><span class="mk"><img src="${IMG}1f9fa.webp" alt=""></span>
      <span class="wm">BasketBuddy<small>FRESH · FAST</small></span></button>
    <button class="loc" data-a="toast" data-v="Delivering across Bengaluru">${I.pin}<span>Bengaluru</span>${I.down}</button>
    <div class="searchbox"><form id="sf" autocomplete="off">${I.search}
      <input id="sq" placeholder="Search fruits, vegetables, groceries…" aria-label="Search products"></form>
      <div class="sugg" id="sg"></div></div>
    <button class="ibtn" data-a="wish" aria-label="Wishlist" id="wishBtn"></button>
    <button class="pill-btn ai" data-a="ai"><img src="${IMG}1f916.webp" alt=""><span>Ask AI</span></button>
    <button class="pill-btn cart" data-a="cart" id="cartBtn"></button>
  </div></header>
  <main class="wrap" id="view"><div class="loading"><img src="${IMG}1f9fa.webp" alt="">Loading fresh picks…</div></main>
  <footer class="foot"><div class="wrap">
    <div><b>BasketBuddy</b> · Fresh groceries, fast.<br>A demo store: no real orders or payments. Not affiliated with BigBasket.</div>
    <div>Product info: BigBasket product list on Kaggle (CC BY-NC-SA 4.0)<br>
      Photos: <a href="https://unsplash.com/?${UTM}" target="_blank" rel="noopener">Unsplash</a> (<button data-a="credits">credits</button>) · Icons: Microsoft Fluent Emoji</div>
  </div></footer>
  <button class="fab" data-a="ai"><span class="bot"><img src="${IMG}1f916.webp" alt=""></span><span>Ask BasketBuddy AI</span></button>
  <div class="scrim" id="scrim" data-a="close"></div>
  <aside class="drawer" id="cartDr" aria-label="Your cart">
    <div class="dh"><button class="back" data-a="close" aria-label="Close">${I.back}</button><h3>Your Cart<small id="cartSub"></small></h3></div>
    <div class="db" id="cartBody"></div><div class="df" id="cartFoot"></div></aside>
  <aside class="drawer ai-dr" id="aiDr" aria-label="AI assistant">
    <div class="dh"><span class="bot"><img src="${IMG}1f916.webp" alt=""></span><h3>BasketBuddy AI
      <small>Your personal shopping assistant</small></h3>
      <button class="back" data-a="close" aria-label="Close">${I.x}</button></div>
    <div class="db" id="chatBody"></div>
    <div class="df"><form class="chat-in" id="cf" autocomplete="off">
      <input id="cq" placeholder="Ask about products, prices, comparisons…" aria-label="Ask the assistant">
      <button class="send" aria-label="Send">${I.send}</button></form>
      <div class="chat-opts"><label id="modeWrap" style="display:none">Retrieval <select id="mode"><option value="hybrid">Hybrid (BM25 + vector)</option>
        <option value="vector">Vector only</option></select></label><span></span><button data-a="clearchat">Clear chat</button></div></div></aside>
  <div class="modal" id="modal"><div class="scrim on" data-a="close"></div><div class="card" id="pd"></div></div>
  <div class="toast" id="toast"></div>`;
  root.appendChild(el);
  const $ = (id) => el.querySelector("#" + id);

  // ------------------------------------------------------------ helpers
  const img = (p) => IMG + (p.img || "1f6d2.webp");
  const photo = (p) => S.photos[(p.img || "").replace(".webp", "").replace("-fe0f", "")];
  const pimg = (p) => { const ph = photo(p); return ph
    ? `<img class="photo" loading="lazy" src="${esc(ph.url)}" alt="${esc(ph.alt)}">`
    : `<img loading="lazy" src="${img(p)}" alt="">`; };
  const catPhoto = (c) => { const k = (S.catImg[c] || "").replace(".webp", "").replace("-fe0f", ""); return S.photos[k]; };
  const qty = (id) => S.cart[id] || 0;
  const wished = (id) => S.wish.includes(id);
  function toast(t) { const n = $("toast"); n.textContent = t; n.classList.add("on"); clearTimeout(S._t);
    S._t = setTimeout(() => n.classList.remove("on"), 1700); }
  function scrollTop() { const sc = document.querySelector('[data-testid="stMain"]');
    try { sc && sc.scrollTo({ top: 0 }); window.scrollTo({ top: 0 }); } catch { /* ignore */ } }
  const addBtn = (p) => qty(p.id)
    ? `<div class="step"><button data-a="dec" data-id="${p.id}" aria-label="Remove one">−</button><span>${qty(p.id)}</span><button data-a="inc" data-id="${p.id}" aria-label="Add one">+</button></div>`
    : `<button class="add" data-a="inc" data-id="${p.id}">Add</button>`;
  const heartBtn = (p) => `<button class="heart ${wished(p.id) ? "on" : ""}" data-a="like" data-id="${p.id}" aria-label="Wishlist">${I.heart}</button>`;
  const rt = (p) => (p.rating ? `<span class="rt">★ ${p.rating.toFixed(1)}</span>` : "");
  function card(p) {
    return `<div class="pc"><div class="ph" data-a="open" data-id="${p.id}">
        ${p.off >= 1 ? `<span class="off">${p.off}% OFF</span>` : ""}<span class="eta">${S.mode === "instant" ? "10 min" : "Tomorrow"}</span>${pimg(p)}</div>
      <div class="nm" data-a="open" data-id="${p.id}" title="${esc(p.name)}">${esc(p.name)}</div>
      <div class="br">${esc(p.brand)} · ${esc(p.type)}</div>
      <div class="pr"><b>${inr(p.price)}</b>${p.mrp > p.price ? `<s>${inr(p.mrp)}</s>` : ""}${rt(p)}</div>
      <div class="act"><span class="hslot" data-id="${p.id}">${heartBtn(p)}</span><span class="aslot" data-id="${p.id}" style="flex:1;display:flex">${addBtn(p)}</span></div></div>`;
  }
  function mcard(p) {
    return `<div class="mcard"><div class="th" data-a="open" data-id="${p.id}">${pimg(p)}</div><div class="n">${esc(p.name)}</div>
      <div class="p">${inr(p.price)}<span class="aslot" data-id="${p.id}">${addBtn(p)}</span></div></div>`;
  }
  const grid = (list) => `<div class="grid">${list.map(card).join("")}</div>`;
  function rail(title, list, act) {
    const id = "r" + Math.random().toString(36).slice(2, 8);
    return `<section class="sec"><div class="sec-h"><h2>${esc(title)}</h2>${act ? `<button data-a="${act.a}" data-v="${esc(act.v || "")}">See all</button>` : ""}</div>
      <div class="rail-wrap"><button class="rail-btn l" data-a="rail" data-r="${id}" data-d="-1">‹</button><div class="rail" id="${id}">${list.map(card).join("")}</div>
      <button class="rail-btn r" data-a="rail" data-r="${id}" data-d="1">›</button></div></section>`;
  }
  function refreshSlots() {
    el.querySelectorAll(".aslot").forEach((s) => { const p = S.byId.get(+s.dataset.id); if (p) s.innerHTML = addBtn(p); });
    el.querySelectorAll(".hslot").forEach((s) => { const p = S.byId.get(+s.dataset.id); if (p) s.innerHTML = heartBtn(p); });
  }

  // ------------------------------------------------------------ cart
  function totals() {
    let items = 0, total = 0, mrp = 0;
    for (const [id, q] of Object.entries(S.cart)) { const p = S.byId.get(+id); if (!p) continue;
      items += q; total += p.price * q; mrp += Math.max(p.mrp, p.price) * q; }
    const c = S.coupon && COUPONS[S.coupon];
    const couponOk = c && total >= c.min;
    const coupon = couponOk ? Math.round(c.calc(total) * 100) / 100 : 0;
    const delivery = items && total < FREE_DELIVERY ? DELIVERY_FEE : 0;
    const handling = items ? HANDLING : 0;
    return { items, total, mrp, coupon, couponOk, delivery, handling, grand: Math.max(0, total - coupon) + delivery + handling };
  }
  function setQty(id, q) {
    if (q <= 0) delete S.cart[id]; else S.cart[id] = q;
    save("bb-cart", S.cart); renderTop(); refreshSlots();
    if ($("cartDr").classList.contains("on")) renderCart();
    if (S.view.name === "checkout") render();
  }
  function renderTop() {
    const t = totals();
    $("cartBtn").innerHTML = `<img src="${IMG}1f6d2.webp" alt="" style="width:22px;height:22px">` +
      (t.items ? `<span class="t"><b>${t.items} item${t.items > 1 ? "s" : ""}</b>${inr(t.total)}</span>` : `<span class="t"><b>Cart</b>empty</span>`) +
      (t.items ? `<span class="badge">${t.items}</span>` : "");
    $("wishBtn").innerHTML = I.heart + (S.wish.length ? `<span class="badge">${S.wish.length}</span>` : "");
  }
  function bill(t) {
    return `<div class="bill"><div><span>Item total (MRP)</span><span>${inr(t.mrp)}</span></div>
      <div class="sv"><span>Product discount</span><span>−${inr(t.mrp - t.total)}</span></div>
      ${t.coupon ? `<div class="sv"><span>Coupon ${esc(S.coupon)}</span><span>−${inr(t.coupon)}</span></div>` : ""}
      <div><span>Delivery fee</span><span>${t.delivery ? inr(t.delivery) : "<b style='color:var(--g)'>FREE</b>"}</span></div>
      <div><span>Handling charge</span><span>${inr(t.handling)}</span></div>
      <div class="tot"><span>To pay</span><span>${inr(t.grand)}</span></div></div>`;
  }
  function couponBox(t) {
    const c = S.coupon && COUPONS[S.coupon];
    const msg = !c ? "" : t.couponOk ? `<div class="cmsg ok">✓ ${esc(S.coupon)} applied: you save ${inr(t.coupon)}</div>`
      : `<div class="cmsg err">${esc(S.coupon)} needs a cart above ${inr(c.min)} (add ${inr(c.min - t.total)} more)</div>`;
    return `<div class="box"><h4>Apply coupon</h4><form class="coupon-in" id="cpf"><input id="cpi" placeholder="Try BUDDY5, FRESH30 or AIPICK" value="${esc(S.coupon || "")}">
      <button>${c ? "Change" : "Apply"}</button></form>${msg}</div>`;
  }
  function beforeCheckout() {
    const picks = S.P.filter((p) => !S.cart[p.id] && p.price <= 60 && p.rating >= 4.2 &&
      (p.cat === "Fruits & Vegetables" || p.cat === "Foodgrains, Oil & Masala" || p.cat === "Bakery, Cakes & Dairy"))
      .sort((a, b) => b.rating - a.rating || a.price - b.price)
      .filter((p, i, arr) => arr.findIndex((x) => x.img === p.img) === i).slice(0, 10);  // varied pictures
    return `<div class="sec-h" style="margin:4px 0 8px"><h2 style="font-size:15px">Before you checkout</h2></div><div class="mini-rail">${picks.map(mcard).join("")}</div>`;
  }
  function renderCart() {
    const t = totals(), ids = Object.keys(S.cart);
    $("cartSub").textContent = t.items ? `${t.items} item${t.items > 1 ? "s" : ""} · saving ${inr(t.mrp - t.total + t.coupon)}` : "";
    if (!ids.length) {
      $("cartBody").innerHTML = `<div class="empty"><div class="ei"><img src="${IMG}1f6d2.webp" alt=""></div><b>Your cart is empty</b>
        <p>Add items from the store, or ask BasketBuddy AI for ideas.</p></div>`;
      $("cartFoot").innerHTML = `<button class="cta" data-a="home" style="justify-content:center">Start shopping</button>`;
      return;
    }
    const gap = FREE_DELIVERY - t.total;
    $("cartBody").innerHTML =
      `<div class="dnote">${S.mode === "instant" ? I.bolt + " Instant delivery · arriving in 10 minutes" : I.clock + " Next day delivery · 7am – 9am slot"}</div>` +
      (gap > 0 ? `<div class="dnote">Add ${inr(gap)} more for FREE delivery</div>` : `<div class="dnote free">🎉 You've unlocked FREE delivery</div>`) +
      ids.map((id) => { const p = S.byId.get(+id); if (!p) return ""; const q = qty(p.id);
        return `<div class="citem"><div class="th">${pimg(p)}</div><div><div class="n">${esc(p.name)}</div>
          <div class="u">${inr(p.price)} / unit × ${q}${p.mrp > p.price ? ` · <s>${inr(p.mrp)}</s>` : ""}</div>
          <div class="rw"><b>Subtotal: ${inr(p.price * q)}</b><span class="aslot" data-id="${p.id}">${addBtn(p)}</span></div></div>
          <button class="trash" data-a="rm" data-id="${p.id}" aria-label="Remove">${I.trash}</button></div>`; }).join("") +
      beforeCheckout() + `<div style="height:12px"></div>` + couponBox(t) + `<div class="box"><h4>Bill details</h4>${bill(t)}</div>`;
    $("cartFoot").innerHTML = `<button class="cta" data-a="checkout"><span>${inr(t.grand)}<small>TOTAL</small></span><span>Proceed to checkout ›</span></button>`;
    const f = $("cpf");
    if (f) f.onsubmit = (e) => { e.preventDefault(); const v = $("cpi").value.trim().toUpperCase();
      if (!v) { S.coupon = null; } else if (!COUPONS[v]) { toast("That coupon code isn't valid"); return; } else S.coupon = v;
      save("bb-coupon", S.coupon); renderCart(); renderTop(); };
  }

  // ------------------------------------------------------------ views
  function greeting() { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; }
  function homeView() {
    const P = S.P, by = (f, s, n) => P.filter(f).sort(s).slice(0, n);
    const deals = by((p) => p.off >= 25 && p.rating >= 4, (a, b) => b.off - a.off, 20);
    const fresh = by((p) => p.cat === "Fruits & Vegetables", (a, b) => (b.rating || 0) - (a.rating || 0) || b.off - a.off, 20);
    const dairy = by((p) => p.cat === "Bakery, Cakes & Dairy" && p.rating, (a, b) => b.rating - a.rating, 20);
    const snacks = by((p) => p.cat === "Snacks & Branded Foods" && p.price <= 50 && p.rating >= 4, (a, b) => b.rating - a.rating, 20);
    const staples = by((p) => p.cat === "Foodgrains, Oil & Masala" && p.rating >= 4, (a, b) => b.off - a.off, 20);
    const beauty = by((p) => p.cat === "Beauty & Hygiene" && p.rating >= 4.2, (a, b) => b.off - a.off, 20);
    return `
    <section class="hero">
      <div class="greet"><div><div class="hi">${greeting()} 👋</div><h1>What can we get you today?</h1>
        <p>${P.length.toLocaleString("en-IN")} groceries and essentials, plus an AI assistant to help you choose.</p></div>
        <div class="modes"><button data-a="mode" data-v="instant" class="${S.mode === "instant" ? "on" : ""}">${I.bolt} Instant delivery</button>
          <button data-a="mode" data-v="nextday" class="${S.mode === "nextday" ? "on" : ""}">${I.clock} Next day</button></div></div>
      <div class="slot"><div class="scooter"><img src="${IMG}1f6f5.webp" alt=""></div><div>
        <span class="tag-new">NEW</span><h2>${S.mode === "instant" ? "Delivery in 10 minutes" : "7am to 9am"}</h2>
        <p>${S.mode === "instant" ? "Express slots are open now in your area." : "Earliest next-day delivery slots available now!"}</p>
        <button class="go" data-a="cat" data-v="Fruits & Vegetables">Shop fresh produce ›</button></div></div>
    </section>
    <section class="coupons">${Object.entries(COUPONS).map(([code, c]) => `<div class="ticket ${c.cls}"><span class="ic">%</span>
      <div class="tx"><b>${esc(c.title)}</b><small>Use ${code} · ${esc(c.sub)}</small></div>
      <button class="ap ${S.coupon === code ? "on" : ""}" data-a="coupon" data-v="${code}">${S.coupon === code ? "Applied" : "Apply"}</button></div>`).join("")}</section>
    <section class="sec"><div class="sec-h"><h2>Categories</h2><button data-a="allcats">See all</button></div><div class="catgrid">
      ${Object.keys(S.cats).slice(0, S.allCats ? 99 : 12).map((c) => { const ph = catPhoto(c);
        return `<button class="ctile" data-a="cat" data-v="${esc(c)}"><div class="ph">${ph ? `<img class="photo" loading="lazy" src="${esc(ph.url)}" alt="${esc(ph.alt)}">`
          : `<img src="${IMG}${S.catImg[c]}" alt="">`}</div><span>${esc(c)}</span><small>${S.cats[c].toLocaleString("en-IN")} items</small></button>`; }).join("")}</div></section>
    ${rail("Today's best deals", deals, { a: "deals", v: "" })}
    ${rail("Fresh fruits & vegetables", fresh, { a: "cat", v: "Fruits & Vegetables" })}
    <section class="sec"><div class="aiband"><div class="bot"><img src="${IMG}1f916.webp" alt=""></div><div>
      <h3>Not sure what to pick? Ask BasketBuddy AI</h3><p>It compares brands, finds deals within your budget, and helps you pick the right product.</p>
      <div class="qchips">${SUGGESTED.slice(0, 4).map((q) => `<button class="qchip" data-a="ask" data-v="${esc(q)}">${esc(q)}</button>`).join("")}</div></div></div></section>
    ${rail("Staples: atta, rice, dals & oils", staples, { a: "cat", v: "Foodgrains, Oil & Masala" })}
    ${rail("Dairy & bakery favourites", dairy, { a: "cat", v: "Bakery, Cakes & Dairy" })}
    ${rail("Snacks under ₹50", snacks, { a: "cat", v: "Snacks & Branded Foods" })}
    ${rail("Personal care on offer", beauty, { a: "deals", v: "Beauty & Hygiene" })}`;
  }
  function applyFilters(list, keepOrder) {
    const f = S.filters, q = S.lq.trim().toLowerCase();
    let out = list.filter((p) => (!f.r4 || p.rating >= 4) && (!f.deal || p.off >= 1) && (!f.u100 || p.price <= 100) &&
      (!q || (p.name + " " + p.brand + " " + p.type).toLowerCase().includes(q)));
    const sorts = { pop: (a, b) => (b.rating || 0) - (a.rating || 0) || b.off - a.off, low: (a, b) => a.price - b.price,
      high: (a, b) => b.price - a.price, off: (a, b) => b.off - a.off, rating: (a, b) => (b.rating || 0) - (a.rating || 0) };
    if (!(keepOrder && f.sort === "pop")) out = out.slice().sort(sorts[f.sort]);
    return out;
  }
  function bar(placeholder, relevance) {
    const f = S.filters;
    return `<div class="bar"><label class="lsearch">${I.search}<input id="lq" value="${esc(S.lq)}" placeholder="${esc(placeholder)}"></label>
      <button class="chip ${f.deal ? "on" : ""}" data-a="flt" data-v="deal">On offer</button>
      <button class="chip ${f.r4 ? "on" : ""}" data-a="flt" data-v="r4">4★ & above</button>
      <button class="chip ${f.u100 ? "on" : ""}" data-a="flt" data-v="u100">Under ₹100</button>
      <select class="sel" id="sortSel">${[["pop", relevance || "Popular"], ["low", "Price: low to high"], ["high", "Price: high to low"], ["off", "Biggest discount"], ["rating", "Top rated"]]
        .map(([v, t]) => `<option value="${v}" ${f.sort === v ? "selected" : ""}>Sort: ${t}</option>`).join("")}</select></div>`;
  }
  const head = (title, n) => `<div class="pagehead"><button class="back" data-a="home" aria-label="Back">${I.back}</button><h1>${title}<small>${n.toLocaleString("en-IN")} items</small></h1></div>`;
  function listView() {
    const v = S.view;
    let base = S.P, title = "", tabs = "", ph = "Search in this list…";
    if (v.name === "cat") {
      base = S.P.filter((p) => p.cat === v.cat);
      const subs = {}; base.forEach((p) => { subs[p.sub] = (subs[p.sub] || 0) + 1; });
      tabs = `<nav class="tabs"><button class="${!v.sub ? "on" : ""}" data-a="sub" data-v="">All</button>${Object.entries(subs).sort((a, b) => b[1] - a[1])
        .map(([s, n]) => `<button class="${v.sub === s ? "on" : ""}" data-a="sub" data-v="${esc(s)}">${esc(s)}<small>${n}</small></button>`).join("")}</nav>`;
      if (v.sub) base = base.filter((p) => p.sub === v.sub);
      title = esc(v.cat); ph = `Search for any ${v.cat.split(/[ ,&]/)[0].toLowerCase()}…`;
    } else if (v.name === "deals") {
      base = S.P.filter((p) => p.off >= 1 && (!v.cat || p.cat === v.cat));
      if (S.filters.sort === "pop") base = base.slice().sort((a, b) => b.off - a.off);
      title = v.cat ? `Deals in ${esc(v.cat)}` : "Best deals";
    } else if (v.name === "ids") { base = v.ids.map((id) => S.byId.get(id)).filter(Boolean); title = esc(v.title); }
    else if (v.name === "wish") { base = S.wish.map((id) => S.byId.get(id)).filter(Boolean); title = "Your wishlist"; }
    const list = applyFilters(base, v.name !== "cat");
    const body = list.length ? grid(list.slice(0, S.listLimit)) +
      (list.length > S.listLimit ? `<button class="more" data-a="more">Show more (${(list.length - S.listLimit).toLocaleString("en-IN")} left)</button>` : "")
      : v.name === "wish" && !S.wish.length
        ? `<div class="empty"><div class="ei">${I.heart}</div><b>No favourites yet</b><p>Tap the heart on any product to save it here.</p></div>`
        : `<div class="empty"><div class="ei"><img src="${IMG}1f50d.webp" alt=""></div><b>No products match</b><p>Try clearing a filter.</p></div>`;
    return head(title, list.length) + tabs + bar(ph) + body;
  }
  function searchView() {
    const q = S.view.q, res = S.search && S.search.q === q ? S.search : null;
    if (!res) return head(`Searching “${esc(q)}”…`, 0) + `<div class="grid">${"<div class='sk'></div>".repeat(10)}</div>`;
    const list = applyFilters(res.ids.map((id) => S.byId.get(id)).filter(Boolean), true);
    return head(`Results for “${esc(q)}”`, list.length) +
      `<div class="ai-hint"><img src="${IMG}1f916.webp" alt=""><div><b>Not sure which one to pick?</b> Ask BasketBuddy AI about “${esc(q)}”.</div>
       <button data-a="ask" data-v="${esc(q)}">Ask AI</button></div>${bar("Refine these results…", "Relevance")}
       ${S.demo ? `<div class="note">Ranked by hybrid search: BM25 keywords + FAISS semantic vectors, fused with RRF.</div>` : ""}
       ${list.length ? grid(list) : `<div class="empty"><div class="ei"><img src="${IMG}1f50d.webp" alt=""></div><b>No products found</b><p>Try another word, or ask the AI.</p></div>`}`;
  }
  function checkoutView() {
    if (S.view.done) return `<div class="done"><div class="ei"><img src="${IMG}1f6f5.webp" alt=""></div><h1>Order placed! 🎉</h1>
      <p>Order <b>#${S.view.done}</b> ${S.view.mode === "instant" ? "is being packed and will arrive in about 10 minutes." : "is scheduled for tomorrow, 7am – 9am."}</p>
      <p class="demo-note">This is a demo store, so no real order was placed.</p>
      <button class="cta" data-a="home" style="max-width:260px;margin:16px auto 0;justify-content:center">Continue shopping</button></div>`;
    const t = totals();
    if (!t.items) return head("Checkout", 0) + `<div class="empty"><div class="ei"><img src="${IMG}1f6d2.webp" alt=""></div><b>Your cart is empty</b></div>`;
    return head("Checkout", t.items) + `<div class="co"><div>
      <div class="box"><h4>Delivery address</h4><div class="opt on">${I.pin}<div><b>Home</b><br><span style="color:var(--muted)">12, 4th Cross, Indiranagar, Bengaluru 560001</span></div></div></div>
      <div class="box"><h4>Delivery slot</h4>
        <button class="opt ${S.mode === "instant" ? "on" : ""}" data-a="mode" data-v="instant" style="width:100%">${I.bolt}<b>Instant · in 10 minutes</b></button>
        <button class="opt ${S.mode === "nextday" ? "on" : ""}" data-a="mode" data-v="nextday" style="width:100%">${I.clock}<b>Next day · 7am – 9am</b></button></div>
      <div class="box"><h4>Payment</h4><div class="opt on">💵 <b>Cash / UPI on delivery</b></div><p class="demo-note">Pay when your order arrives.</p></div></div>
      <div><div class="box"><h4>Order summary · ${t.items} items</h4>${bill(t)}</div>
      <button class="cta" data-a="place"><span>${inr(t.grand)}<small>TOTAL</small></span><span>Place order ›</span></button></div></div>`;
  }
  function render() {
    if (!S.ready) return;
    const v = S.view.name;
    $("view").innerHTML = v === "home" ? homeView() : v === "search" ? searchView() : v === "checkout" ? checkoutView() : listView();
    const sel = $("view").querySelector("#sortSel");
    if (sel) sel.onchange = () => { S.filters.sort = sel.value; S.listLimit = 40; render(); };
    const lq = $("view").querySelector("#lq");
    if (lq) lq.oninput = () => { S.lq = lq.value; S.listLimit = 40; const pos = lq.selectionStart; render();
      const n = $("view").querySelector("#lq"); n.focus(); try { n.setSelectionRange(pos, pos); } catch { /* ignore */ } };
  }
  function go(view) { S.view = view; S.listLimit = 40; S.lq = ""; closeAll(); render(); scrollTop(); }
  const resetFilters = () => { S.filters = { sort: "pop", r4: false, deal: false, u100: false }; };

  // ------------------------------------------------------------ product modal
  function openProduct(id) {
    const p = S.byId.get(id); if (!p) return;
    if (S.details[id] == null && !S.detailsSent.has(id)) { S.detailsSent.add(id); S.trigger("details", id); }
    const ph = photo(p);
    $("pd").innerHTML = `<button class="x" data-a="close" aria-label="Close">${I.x}</button>
      <div class="pd-ph">${p.off >= 1 ? `<span class="off" style="top:16px;left:16px">${p.off}% OFF</span>` : ""}${pimg(p)}</div>
      <div class="pd"><div class="crumbs">${esc(p.cat)} › ${esc(p.sub)} › ${esc(p.type)}</div><h2>${esc(p.name)}</h2>
        <span class="brand">${esc(p.brand)}</span> ${p.rating ? `· ${rt(p)}` : `<span class="crumbs">· Not rated</span>`}
        <div class="prow"><b>${inr(p.price)}</b>${p.mrp > p.price ? `<s>MRP ${inr(p.mrp)}</s><span class="offp">${p.off}% OFF</span>` : ""}</div>
        <div class="tax">Inclusive of all taxes · ${S.mode === "instant" ? "⚡ Delivery in 10 minutes" : "🕖 Next day, 7am – 9am"}</div>
        <div class="act"><span class="aslot" data-id="${p.id}" style="display:flex">${addBtn(p)}</span><span class="hslot" data-id="${p.id}">${heartBtn(p)}</span>
          <button class="ask" data-a="ask" data-v="${esc(`Tell me about ${p.name} by ${p.brand}: what is it, its price and rating?`)}">✨ Ask AI</button></div>
        <h4>Product details</h4><div class="desc" id="pdDesc">${S.details[id] != null ? esc(S.details[id]) : "Loading description…"}</div>
        <h4>Information</h4><div class="facts"><span>Brand</span><span>${esc(p.brand)}</span><span>Category</span><span>${esc(p.cat)}</span>
          <span>Type</span><span>${esc(p.type)}</span></div>
        ${ph ? `<p class="credit">Representative photo by
          <a href="${esc(ph.author_url)}" target="_blank" rel="noopener">${esc(ph.author)}</a> on
          <a href="${esc(ph.unsplash_url)}" target="_blank" rel="noopener">Unsplash</a></p>` : ""}</div>`;
    $("modal").classList.add("on"); S.openPid = id;
  }

  // ------------------------------------------------------------ chat
  function renderChat() {
    let h = "";
    if (!S.chat.length && !S.pendingQ) h = `<div class="welcome"><div class="bot"><img src="${IMG}1f916.webp" alt=""></div><h4>Hi! I'm BasketBuddy AI</h4>
      <p>Ask me about products, prices, brands and deals. I’ll find the best options for you.</p>
      <div class="qchips">${SUGGESTED.map((q) => `<button class="qchip" data-a="ask" data-v="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>`;
    S.chat.forEach((m, i) => {
      if (m.role === "user") { h += `<div class="msg u"><div class="bub">${esc(m.content)}</div></div>`; return; }
      const meta = m.meta || {}, prods = (m.ids || []).map((id) => S.byId.get(id)).filter(Boolean);
      const kv = [["Best similarity", `${(meta.best || 0).toFixed(2)} (threshold ${meta.threshold})`], ["Retrieval", meta.mode],
        ["Products used", String(prods.length)], ["Time", `${(meta.seconds || 0).toFixed(1)} s`]];
      if (meta.sub_queries && meta.sub_queries.length) kv.push(["Decomposition", meta.sub_queries.join(" · ")]);
      if (meta.filter && (meta.filter[0] != null || meta.filter[1] != null)) kv.push(["Price filter", `₹${meta.filter[0] || 0} – ${meta.filter[1] != null ? "₹" + meta.filter[1] : "any"}`]);
      if (meta.sort) kv.push(["Sorted by", `${meta.sort[0].replace("_", " ")} (${meta.sort[1] ? "high → low" : "low → high"})`]);
      if (meta.model) kv.push(["Model", meta.model]);
      if (meta.fallback) kv.push(["Guardrail", "Below threshold, so the LLM was not called"]);
      h += `<div class="msg a"><div class="bub ${meta.fallback ? "fb" : ""}">${md(m.content)}
        ${!meta.fallback && prods.length ? `<div class="mini-rail">${prods.map(mcard).join("")}</div>
          <div class="links"><button data-a="showids" data-i="${i}">View these ${prods.length} in the store ›</button></div>` : ""}
        ${S.demo ? `<details class="rd"><summary>How I found this</summary><div class="kv">${kv.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join("")}</div></details>` : ""}</div></div>`;
    });
    if (S.pendingQ) h += `<div class="msg u"><div class="bub">${esc(S.pendingQ)}</div></div><div><span class="typing"><i></i><i></i><i></i></span>
      <div class="typing-l">Finding the best options for you…</div></div>`;
    const b = $("chatBody"); b.innerHTML = h; b.scrollTop = b.scrollHeight;
  }
  function ask(q) {
    q = (q || "").trim(); if (!q || S.pendingQ) return;
    openDrawer("aiDr"); S.pendingQ = q; S.chatSent = { n: S.chat.length }; renderChat();
    S.trigger("ask", { q, mode: $("mode").value, nonce: Date.now() });
  }

  // ------------------------------------------------------------ drawers
  function openDrawer(id) {
    $("modal").classList.remove("on");
    ["cartDr", "aiDr"].forEach((d) => $(d).classList.toggle("on", d === id));
    $("scrim").classList.add("on");
    if (id === "cartDr") renderCart(); else { renderChat(); setTimeout(() => $("cq").focus(), 250); }
  }
  function closeAll() { ["cartDr", "aiDr"].forEach((d) => $(d).classList.remove("on")); $("scrim").classList.remove("on");
    $("modal").classList.remove("on"); S.openPid = null; }

  // ------------------------------------------------------------ search + suggestions
  const sq = $("sq"), sg = $("sg");
  function suggest() {
    const q = sq.value.trim().toLowerCase();
    if (q.length < 2 || !S.ready) { sg.classList.remove("on"); return; }
    const words = q.split(/\s+/), hits = [];
    for (const p of S.P) { const s = (p.name + " " + p.brand).toLowerCase(); if (words.every((w) => s.includes(w))) { hits.push(p); if (hits.length >= 6) break; } }
    sg.innerHTML = hits.map((p) => `<button data-a="open" data-id="${p.id}"><span class="th">${pimg(p)}</span><span>${esc(p.name)}<small>${esc(p.brand)} · ${inr(p.price)}</small></span></button>`).join("") +
      `<button class="ai" data-a="ask" data-v="${esc(sq.value.trim())}">✨ Ask AI about “${esc(sq.value.trim())}”</button>`;
    sg.classList.add("on");
  }
  sq.addEventListener("input", suggest); sq.addEventListener("focus", suggest);
  sq.addEventListener("blur", () => setTimeout(() => sg.classList.remove("on"), 180));
  $("sf").addEventListener("submit", (e) => { e.preventDefault(); const q = sq.value.trim(); if (!q) return;
    sg.classList.remove("on"); sq.blur(); resetFilters(); go({ name: "search", q });
    if (!(S.search && S.search.q === q)) S.trigger("search", { q, nonce: Date.now() }); });
  $("cf").addEventListener("submit", (e) => { e.preventDefault(); const v = $("cq").value; $("cq").value = ""; ask(v); });
  el.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAll(); });

  // ------------------------------------------------------------ clicks
  el.addEventListener("click", (e) => {
    const t = e.target.closest("[data-a]"); if (!t) return;
    const a = t.dataset.a, v = t.dataset.v, id = t.dataset.id != null ? +t.dataset.id : null;
    switch (a) {
      case "home": go({ name: "home" }); break;
      case "cat": resetFilters(); go({ name: "cat", cat: v }); break;
      case "sub": S.view = { ...S.view, sub: v || null }; S.listLimit = 40; render(); break;
      case "deals": resetFilters(); go({ name: "deals", cat: v || null }); break;
      case "allcats": S.allCats = !S.allCats; render(); break;
      case "flt": S.filters[v] = !S.filters[v]; S.listLimit = 40; render(); break;
      case "more": S.listLimit += 40; render(); break;
      case "inc": { const was = qty(id); setQty(id, was + 1); if (!was) toast("Added to cart"); break; }
      case "dec": setQty(id, qty(id) - 1); break;
      case "rm": setQty(id, 0); break;
      case "like": { const on = wished(id); S.wish = on ? S.wish.filter((x) => x !== id) : [id, ...S.wish]; save("bb-wish", S.wish);
        renderTop(); refreshSlots(); toast(on ? "Removed from wishlist" : "Saved to wishlist"); if (S.view.name === "wish") render(); break; }
      case "wish": resetFilters(); go({ name: "wish" }); break;
      case "coupon": S.coupon = S.coupon === v ? null : v; save("bb-coupon", S.coupon); render(); renderTop();
        toast(S.coupon ? `${v} will be applied in your cart` : "Coupon removed"); break;
      case "mode": S.mode = v; save("bb-mode", v); render(); if ($("cartDr").classList.contains("on")) renderCart();
        toast(v === "instant" ? "Instant delivery selected" : "Next day delivery selected"); break;
      case "open": sg.classList.remove("on"); openProduct(id); break;
      case "cart": openDrawer("cartDr"); break;
      case "ai": openDrawer("aiDr"); break;
      case "ask": sg.classList.remove("on"); $("modal").classList.remove("on"); ask(v); break;
      case "close": closeAll(); break;
      case "toast": toast(v); break;
      case "clearchat": S.trigger("clearchat", Date.now()); S.chat = []; renderChat(); break;
      case "showids": { const m = S.chat[+t.dataset.i]; resetFilters(); go({ name: "ids", ids: m.ids, title: "From your AI answer" }); break; }
      case "rail": { const r = el.querySelector("#" + t.dataset.r); r && r.scrollBy({ left: +t.dataset.d * r.clientWidth * 0.8 }); break; }
      case "checkout": go({ name: "checkout" }); break;
      case "place": { const no = "BB" + Math.floor(100000 + Math.random() * 900000); S.cart = {}; save("bb-cart", S.cart);
        S.coupon = null; save("bb-coupon", null); renderTop(); S.view = { name: "checkout", done: no, mode: S.mode }; render(); scrollTop(); break; }
      case "classic": S.trigger("nav", "classic"); break;
      case "credits": {
        $("pd").innerHTML = `<button class="x" data-a="close">${I.x}</button><div class="pd" style="grid-column:1/-1"><h2>Photo credits</h2>
          <p class="credit">Product photos are illustrative photos of each product type, hotlinked from
          <a href="https://unsplash.com/?${UTM}" target="_blank" rel="noopener">Unsplash</a>. Products without a photo use Microsoft Fluent Emoji 3D illustrations (MIT).</p>
          <div class="credits">${Object.values(S.photos).map((c) => `<a href="${esc(c.photo_url)}" target="_blank" rel="noopener"><img src="${esc(c.url)}" alt="${esc(c.alt)}" loading="lazy">
            <span>${esc(c.query)}<small>by ${esc(c.author)}</small></span></a>`).join("")}</div></div>`;
        $("modal").classList.add("on"); break;
      }
    }
  });

  // ------------------------------------------------------------ data from Python
  S.update = (data) => {
    S.data = data || {};
    // Presenter view (?demo=1): show retrieval internals for the class demo; hidden for shoppers.
    if (!!S.data.demo !== S.demo) { S.demo = !!S.data.demo; $("modeWrap").style.display = S.demo ? "" : "none"; render(); renderChat(); }
    if (S.data.search && (!S.search || S.data.search.nonce !== S.search.nonce)) {
      S.search = S.data.search; if (S.view.name === "search" && S.view.q === S.search.q) render(); }
    if (Array.isArray(S.data.chat)) {
      const grew = S.data.chat.length !== S.chat.length; S.chat = S.data.chat;
      if (S.pendingQ && S.chatSent && S.chat.length > S.chatSent.n) S.pendingQ = null;
      if (grew || !S.pendingQ) renderChat(); }
    if (S.data.details) {
      for (const [k, txt] of Object.entries(S.data.details)) S.details[k] = txt;
      if (S.openPid != null && S.details[S.openPid] != null) { const d = $("pdDesc"); if (d) d.textContent = S.details[S.openPid]; } }
  };

  // ------------------------------------------------------------ boot
  fetch(CATALOG).then((r) => r.json()).then((j) => {
    S.P = j.rows.map((r) => Object.fromEntries(j.fields.map((f, i) => [f, r[i]])));
    S.P.forEach((p) => { S.byId.set(p.id, p); S.cats[p.cat] = (S.cats[p.cat] || 0) + 1; });
    S.cats = Object.fromEntries(Object.entries(S.cats).sort((a, b) => b[1] - a[1]));
    S.catImg = j.cats || {};
    S.wish = S.wish.filter((id) => S.byId.has(id));
    S.ready = true; renderTop(); render(); S.update(S.data);
    fetch(PHOTOS).then((r) => (r.ok ? r.json() : {})).then((ph) => { S.photos = ph || {}; render(); }).catch(() => {});
  }).catch(() => { $("view").innerHTML = `<div class="empty"><b>Couldn't load the store.</b><p>Please refresh the page.</p></div>`; });

  return S;
}

export default function (component) {
  const { parentElement, data, setTriggerValue } = component;
  let S = parentElement.__bb;
  if (!S) S = parentElement.__bb = createApp(parentElement);
  S.trigger = setTriggerValue;
  S.update(data);
}
