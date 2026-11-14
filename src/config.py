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
# If the best semantic (cosine) match is below this, we answer with the fallback
# message without calling the LLM. Tuned on test questions (see README).
RELEVANCE_THRESHOLD = 0.60

# --- LLM (OpenRouter, OpenAI-compatible API) -------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
# Free models are rate limited and change often: try these in order on failure.
FALLBACK_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]


def get_api_key() -> str | None:
    """Read the OpenRouter key from the environment or Streamlit secrets."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("OPENROUTER_API_KEY")
    except Exception:
        return None
