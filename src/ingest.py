"""Data -> cleaning -> chunking -> embeddings -> FAISS vector store.

Run once (takes a few minutes on CPU):
    python -m src.ingest
"""
import re
import time

import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, CLEAN_CSV, INDEX_DIR, RAW_CSV
from src.embeddings import get_embeddings


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Remove empty, duplicate and malformed records."""
    n0 = len(df)
    df = df.drop(columns=["index"], errors="ignore")
    for col in ["product", "category", "sub_category", "brand", "type", "description"]:
        df[col] = df[col].astype("string").str.strip()
        df[col] = df[col].str.replace(r"\s+", " ", regex=True)
    df = df.dropna(subset=["product", "description"])
    df = df[df["description"].str.len() > 20]               # too short to be useful
    df["brand"] = df["brand"].fillna("Unbranded")
    df = df.drop_duplicates(subset=["product", "brand", "sale_price", "market_price", "description"])
    df = df[(df["sale_price"] > 0) & (df["market_price"] > 0)]
    df["discount_pct"] = ((df["market_price"] - df["sale_price"]) / df["market_price"] * 100).round(0).clip(lower=0)
    df = df.reset_index(drop=True)
    df.insert(0, "product_id", df.index)
    print(f"Cleaning: {n0} -> {len(df)} rows ({n0 - len(df)} removed)")
    return df


def header(r) -> str:
    rating = f"{r.rating}/5" if pd.notna(r.rating) else "Not rated"
    price = f"₹{r.sale_price:g}"
    if r.market_price > r.sale_price:
        price += f" (MRP ₹{r.market_price:g}, {r.discount_pct:g}% off)"
    return (
        f"Product: {r['product']}\n"
        f"Brand: {r.brand}\n"
        f"Category: {r.category} > {r.sub_category} > {r.type}\n"
        f"Price: {price}\n"
        f"Rating: {rating}"
    )


def build_documents(df: pd.DataFrame) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ". ", " ", ""]
    )
    docs = []
    for r in df.itertuples(index=False):
        r = pd.Series(r._asdict())
        head = header(r)
        pieces = splitter.split_text(r.description)
        meta = {
            "product_id": int(r.product_id),
            "product": r["product"],
            "brand": r.brand,
            "category": r.category,
            "sub_category": r.sub_category,
            "type": r.type,
            "sale_price": float(r.sale_price),
            "market_price": float(r.market_price),
            "discount_pct": float(r.discount_pct),
            "rating": None if pd.isna(r.rating) else float(r.rating),
        }
        for i, piece in enumerate(pieces):
            text = f"{head}\nDescription: {piece}"
            docs.append(Document(page_content=text, metadata={**meta, "chunk": i, "n_chunks": len(pieces)}))
    return docs


def main():
    df = clean(pd.read_csv(RAW_CSV))
    CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)

    docs = build_documents(df)
    multi = sum(1 for d in docs if d.metadata["n_chunks"] > 1 and d.metadata["chunk"] == 0)
    print(f"Chunking: {len(df)} products -> {len(docs)} chunks ({multi} long products split)")

    t = time.time()
    store = FAISS.from_documents(
        docs, get_embeddings(), distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
    )
    INDEX_DIR.parent.mkdir(parents=True, exist_ok=True)
    store.save_local(str(INDEX_DIR))
    print(f"Embeddings + FAISS: {store.index.ntotal} vectors in {time.time() - t:.0f}s -> {INDEX_DIR}")


if __name__ == "__main__":
    main()
