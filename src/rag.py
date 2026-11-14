"""Retrieval (hybrid BM25 + FAISS) -> context -> LLM -> grounded answer."""
import re
from dataclasses import dataclass, field

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


@dataclass
class RAGResult:
    answer: str
    docs: list[Document] = field(default_factory=list)
    best_score: float = 0.0
    price_filter: tuple = (None, None)
    used_fallback: bool = False
    model: str | None = None


class BigBasketRAG:
    def __init__(self):
        self.vectorstore = FAISS.load_local(
            str(config.INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True
        )
        # Build the keyword index from the same chunks that are in FAISS.
        all_docs = list(self.vectorstore.docstore._dict.values())
        self.bm25 = BM25Retriever.from_documents(all_docs, k=config.CANDIDATE_POOL)
        self.llm = self._build_llm()

    # ---------------------------------------------------------------- LLM
    def _build_llm(self):
        key = config.get_api_key()
        if not key:
            return None

        def make(model):
            return ChatOpenAI(
                model=model, base_url=config.OPENROUTER_BASE_URL, api_key=key,
                temperature=0, max_tokens=700, timeout=60, max_retries=1,
            )

        primary = make(config.PRIMARY_MODEL)
        return primary.with_fallbacks([make(m) for m in config.FALLBACK_MODELS])

    # ---------------------------------------------------------- retrieval
    def retrieve(self, question: str, mode: str = "hybrid", k: int = config.TOP_K):
        """Return (docs, best_semantic_score, price_filter)."""
        lo, hi = parse_price_filter(question)

        vec = self.vectorstore.similarity_search_with_score(question, k=config.CANDIDATE_POOL)
        best_score = max((s for _, s in vec), default=0.0)
        vec_docs = [d for d, _ in vec]

        if mode == "hybrid":
            kw_docs = self.bm25.invoke(question)
            ranked = self._rrf([vec_docs, kw_docs])
        else:
            ranked = vec_docs

        if lo is not None or hi is not None:
            ranked = [
                d for d in ranked
                if (lo is None or d.metadata["sale_price"] >= lo)
                and (hi is None or d.metadata["sale_price"] <= hi)
            ]
        return ranked[:k], float(best_score), (lo, hi)

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
        docs, best, pf = self.retrieve(question, mode, k)

        # Fallback layer 1: nothing relevant enough in the catalogue.
        if best < config.RELEVANCE_THRESHOLD or not docs:
            return RAGResult(FALLBACK_MESSAGE, docs, best, pf, used_fallback=True)

        if self.llm is None:
            return RAGResult("⚠️ OPENROUTER_API_KEY is not set, so I can't generate an answer. "
                             "The retrieved products are shown below.", docs, best, pf)

        context = "\n\n---\n\n".join(d.page_content for d in docs)
        if pf != (None, None):
            context = f"(Products were pre-filtered to price range: {pf[0] or 0} – {pf[1] or 'any'} ₹)\n\n" + context

        try:
            msg = (PROMPT | self.llm).invoke({"context": context, "question": question})
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            model = (msg.response_metadata or {}).get("model_name")
        except Exception as e:  # rate limits / provider errors on free models
            return RAGResult(f"⚠️ The language model is unavailable right now ({type(e).__name__}). "
                             "Please retry in a moment. Retrieved products are shown below.", docs, best, pf)
        # Fallback layer 2 is in the prompt (rule 4): the LLM says when context is insufficient.
        return RAGResult(text.strip(), docs, best, pf, model=model)
