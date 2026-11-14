"""Embedding model shared by ingestion and query time (must be identical)."""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.embeddings import FastEmbedEmbeddings  # noqa: E402

from src.config import EMBED_MODEL  # noqa: E402


def get_embeddings() -> FastEmbedEmbeddings:
    # Vectors are L2-normalised, so FAISS inner product = cosine similarity.
    return FastEmbedEmbeddings(model_name=EMBED_MODEL, batch_size=64)
