"""Retrieval (hybrid BM25 + FAISS) -> context -> LLM -> grounded answer."""
import re
import time
from dataclasses import dataclass, field
from itertools import zip_longest

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src import config
from src.embeddings import get_embeddings

FALLBACK_MESSAGE = (
    "I couldn't find information about that in the BigBasket product catalogue. "
    "I can only answer questions about products, brands, categories, prices, discounts, "
    "ratings and product descriptions available in the dataset."
)

SYSTEM_PROMPT = """You are the BigBasket Product Assistant, helping shoppers on an Indian online grocery store.

Rules:
1. Answer ONLY using the product context below. Do not use outside knowledge about products, prices, brands or BigBasket's services.
2. Always mention the exact product name and brand you are referring to. Prices are in Indian Rupees (₹).
3. For comparisons, compare only on attributes present in the context (price, MRP, discount, rating, description).
4. If the context does not contain the information needed (e.g. delivery times, stock, return policy, offers, nutrition values not stated), reply that the catalogue does not have that information. Do not guess. If only part of the question can be answered, answer that part and say which part is not covered.
5. If a product is "Not rated", say so; never invent ratings.
6. Keep answers concise; use a short list or table when listing several products.

Product context:
{context}"""

PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{question}")])

_NUM = r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)"
MAX_PATTERNS = [rf"(?:under|below|less than|cheaper than|within|upto|up to|max(?:imum)?|<)\s*{_NUM}"]
MIN_PATTERNS = [rf"(?:above|over|more than|greater than|at least|min(?:imum)?|>)\s*{_NUM}"]


def parse_price_filter(question: str) -> tuple[float | None, float | None]:
    """Extract a price range like 'under ₹100' / 'between 50 and 200'."""
    q = question.lower().replace(",", "")
    m = re.search(rf"between\s*{_NUM}\s*(?:and|to|-)\s*{_NUM}", q)
    if m:
        lo, hi = sorted([float(m.group(1)), float(m.group(2))])
        return lo, hi
    lo = hi = None
    for p in MAX_PATTERNS:
        if m := re.search(p, q):
            hi = float(m.group(1))
    for p in MIN_PATTERNS:
        if m := re.search(p, q):
            lo = float(m.group(1))
    return lo, hi


STOPWORDS = set("""a an the is are was of for to in on and or vs versus with what which who how
do does i me my you your please tell show suggest give find get some any can could should
compare comparison between price cost much than it its this that these those""".split())


def bm25_tokenize(text: str) -> list[str]:
    """Lower-case word tokens without punctuation or filler words ("Yippee?" -> "yippee")."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


_TAIL = r"(?:\s+(?:on|by|in terms of|based on|for|regarding)\s+.*)?$"
COMPARE_PATTERNS = [
    rf"compare\s+(.+?)\s+(?:and|with|to|vs\.?|versus)\s+(.+?){_TAIL}",
    rf"(?:difference|differences)\s+between\s+(.+?)\s+and\s+(.+?){_TAIL}",
    rf"(?:cheaper|better|healthier|costlier)\s*[:,]?\s+(.+?)\s+or\s+(.+?){_TAIL}",
    rf"^(.+?)\s+(?:vs\.?|versus)\s+(.+?){_TAIL}",
]


def decompose_comparison(question: str) -> list[str]:
    """Query decomposition: 'Compare X and Y on price' -> ['X', 'Y'] (empty if not a comparison)."""
    q = question.lower().strip().rstrip("?.!")
    for p in COMPARE_PATTERNS:
        if m := re.search(p, q):
            parts = [s.strip(" ,:") for s in m.groups() if s and s.strip(" ,:")]
            if len(parts) == 2:
                return parts
    return []


SORT_RULES = [
    (r"cheapest|lowest price|least expensive|most affordable|budget", ("sale_price", False)),
    (r"most expensive|costliest|highest price", ("sale_price", True)),
    (r"(?:highest|biggest|best|maximum|most|largest)\s+(?:discount|deal|offer|savings?)", ("discount_pct", True)),
    (r"(?:best|highest|top)[ -]rated|highest rating|best rating", ("rating", True)),
]


def detect_sort(question: str):
    q = question.lower()
    for pattern, rule in SORT_RULES:
        if re.search(pattern, q):
            return rule
    return None


def dedupe(docs: list[Document]) -> list[Document]:
    """Keep one chunk per product listing (same name, brand and price)."""
    seen, out = set(), []
    for d in docs:
        m = d.metadata
        key = (m["product"].lower(), m["brand"].lower(), m["sale_price"])
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


@dataclass
class RAGResult:
    answer: str
    docs: list[Document] = field(default_factory=list)
    best_score: float = 0.0
    price_filter: tuple = (None, None)
    used_fallback: bool = False
    model: str | None = None
    sub_queries: list[str] = field(default_factory=list)  # query decomposition, if any
    sort: tuple | None = None                              # (field, descending) if re-sorted
    seconds: float = 0.0


class BigBasketRAG:
    def __init__(self):
        self.vectorstore = FAISS.load_local(
            str(config.INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True
        )
        # Build the keyword index from the same chunks that are in FAISS.
        all_docs = list(self.vectorstore.docstore._dict.values())
        self.bm25 = BM25Retriever.from_documents(
            all_docs, k=config.CANDIDATE_POOL, preprocess_func=bm25_tokenize
        )
        self.llm = self._build_llm()

    # ---------------------------------------------------------------- LLM
    def _build_llm(self):
        """Ordered list of chat models: primary first, then fallbacks."""
        models = []
        for provider, model in config.MODEL_CHAIN:
            p = config.PROVIDERS[provider]
            key = config.get_secret(p["key_name"])
            if not key:
                continue  # provider not configured
            models.append(ChatOpenAI(
                model=model, base_url=p["base_url"], api_key=key,
                temperature=0, max_tokens=2000, timeout=45, max_retries=0,
                # Reasoning models otherwise spend the whole budget "thinking".
                extra_body=p["extra_body"],
            ))
        return models or None

    def _generate(self, context: str, question: str) -> tuple[str, str]:
        """Try each model in turn; skip ones that error (e.g. 429) or return an empty/cut-off answer."""
        errors = []
        for llm in self.llm:
            try:
                msg = (PROMPT | llm).invoke({"context": context, "question": question})
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
                if text.strip() and msg.response_metadata.get("finish_reason") != "length":
                    return text.strip(), llm.model_name
                errors.append(f"{llm.model_name}: empty/truncated")
            except Exception as e:
                errors.append(f"{llm.model_name}: {type(e).__name__}")
        raise RuntimeError("; ".join(errors))

    # ---------------------------------------------------------- retrieval
    def _search(self, query: str, mode: str) -> tuple[list[Document], float]:
        """One retrieval pass: vector (+ BM25 fused with RRF in hybrid mode)."""
        vec = self.vectorstore.similarity_search_with_score(query, k=config.CANDIDATE_POOL)
        best = max((s for _, s in vec), default=0.0)
        vec_docs = [d for d, _ in vec]
        if mode == "hybrid":
            return self._rrf([vec_docs, self.bm25.invoke(query)]), float(best)
        return vec_docs, float(best)

    def retrieve(self, question: str, mode: str = "hybrid", k: int = config.TOP_K):
        """Return (docs, best_semantic_score, price_filter).

        Steps: query decomposition for comparisons -> hybrid search per sub-query ->
        price filter -> de-duplicate -> optional sort by price/discount/rating.
        """
        lo, hi = parse_price_filter(question)

        ranked, best = self._search(question, mode)
        sub_queries = decompose_comparison(question)
        if sub_queries:
            # Interleave results so every compared item is represented in the top-k.
            lists = [self._search(sq, mode)[0] for sq in sub_queries] + [ranked]
            ranked = [d for group in zip_longest(*lists) for d in group if d is not None]

        if lo is not None or hi is not None:
            ranked = [
                d for d in ranked
                if (lo is None or d.metadata["sale_price"] >= lo)
                and (hi is None or d.metadata["sale_price"] <= hi)
            ]

        ranked = dedupe(ranked)
        if sort := detect_sort(question):
            key, reverse = sort
            window = ranked[:config.SORT_WINDOW]  # sort only among relevant candidates
            window.sort(key=lambda d: (d.metadata.get(key) is None,
                                       -(d.metadata.get(key) or 0) if reverse else (d.metadata.get(key) or 0)))
            ranked = window + ranked[config.SORT_WINDOW:]
        return ranked[:k], best, (lo, hi)

    @staticmethod
    def _rrf(result_lists: list[list[Document]]) -> list[Document]:
        """Reciprocal Rank Fusion: score = sum(1 / (RRF_K + rank))."""
        scores, by_key = {}, {}
        for docs in result_lists:
            for rank, d in enumerate(docs):
                key = (d.metadata["product_id"], d.metadata["chunk"])
                by_key[key] = d
                scores[key] = scores.get(key, 0.0) + 1.0 / (config.RRF_K + rank + 1)
        return [by_key[k] for k in sorted(scores, key=scores.get, reverse=True)]

    # -------------------------------------------------------------- answer
    def answer(self, question: str, mode: str = "hybrid", k: int = config.TOP_K) -> RAGResult:
        t0 = time.time()
        res = self._answer(question, mode, k)
        res.sub_queries = decompose_comparison(question)
        res.sort = detect_sort(question)
        res.seconds = time.time() - t0
        return res

    def _answer(self, question: str, mode: str, k: int) -> RAGResult:
        docs, best, pf = self.retrieve(question, mode, k)

        # Fallback layer 1: nothing relevant enough in the catalogue.
        if best < config.RELEVANCE_THRESHOLD or not docs:
            return RAGResult(FALLBACK_MESSAGE, docs, best, pf, used_fallback=True)

        if self.llm is None:
            return RAGResult("⚠️ No LLM API key is configured (OPENROUTER_API_KEY or GEMINI_API_KEY), "
                             "so I can't generate an answer. The retrieved products are shown below.",
                             docs, best, pf)

        context = "\n\n---\n\n".join(d.page_content for d in docs)
        if pf != (None, None):
            context = f"(Products were pre-filtered to price range: {pf[0] or 0} – {pf[1] or 'any'} ₹)\n\n" + context

        try:
            text, model = self._generate(context, question)
        except Exception as e:  # every model rate-limited / failing (free tier)
            return RAGResult(f"⚠️ The language models are unavailable right now ({e}). "
                             "Please retry in a moment. Retrieved products are shown below.", docs, best, pf)
        # Fallback layer 2 is in the prompt (rule 4): the LLM says when context is insufficient.
        return RAGResult(text, docs, best, pf, model=model)
