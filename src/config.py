"""Central configuration for the BigBasket RAG chatbot."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "BigBasket_Products.csv"
CLEAN_CSV = ROOT / "data" / "processed" / "products_clean.csv"
INDEX_DIR = ROOT / "vectorstore" / "faiss_index"

# --- Embeddings -------------------------------------------------------------
# Small, fast, free; runs locally on CPU (ONNX via FastEmbed). 384-dim, max 256 tokens.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# --- Chunking ---------------------------------------------------------------
# One document per product. Only descriptions longer than CHUNK_SIZE characters
# are split; every piece repeats the product header so it stays self-contained.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# --- Retrieval --------------------------------------------------------------
TOP_K = 6            # chunks passed to the LLM
CANDIDATE_POOL = 40  # candidates fetched from each retriever before fusion/filtering
RRF_K = 60           # reciprocal-rank-fusion constant (standard value)
SORT_WINDOW = 15     # for "cheapest"/"highest discount"/"best rated": re-sort this many top hits
# If the best semantic (cosine) match is below this, we answer with the fallback
# message without calling the LLM. Tuned on test questions: in-catalogue questions
# scored 0.61-0.72, off-topic ones 0.21-0.40 (see README).
RELEVANCE_THRESHOLD = 0.45

# --- LLMs ------------------------------------------------------------------
# Every provider below exposes an OpenAI-compatible API, so one client class works
# for all of them. Models are tried in order; one that is rate-limited (429) or
# returns an empty/truncated answer is skipped. Providers without a key are skipped.
PROVIDERS = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_name": "OPENROUTER_API_KEY",
                   "extra_body": {"reasoning": {"effort": "low"}}},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "key_name": "GEMINI_API_KEY", "extra_body": {"reasoning_effort": "low"}},
}
MODEL_CHAIN = [
    ("openrouter", os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")),
    ("openrouter", "google/gemma-4-31b-it:free"),
    ("gemini", "gemini-3.5-flash"),
    ("gemini", "gemini-flash-lite-latest"),
    ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
]
PRIMARY_MODEL = MODEL_CHAIN[0][1]


def get_secret(name: str) -> str | None:
    """Read a key from the environment / .env, or from Streamlit secrets when deployed."""
    if os.getenv(name):
        return os.getenv(name)
    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        return None
