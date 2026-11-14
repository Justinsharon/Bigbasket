# 🛒 BigBasket Product Assistant — RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that helps shoppers discover and compare
products in **BigBasket's** online grocery catalogue. Answers are grounded only in the
retrieved product records; when the catalogue doesn't contain the answer, the bot says so.

**Industry:** Food & Grocery · **Company:** BigBasket
**User:** an online grocery shopper · **Purpose:** product discovery, comparison and Q&A
(price, MRP, discount, brand, rating, description/usage).

## Dataset
| | |
|---|---|
| Source | Kaggle — *BigBasket Entire Product List (~28K datapoints)* |
| License | CC BY-NC-SA 4.0 (non-commercial, attribution, share-alike) |
| Raw | 27,555 rows · 10 columns (`product, category, sub_category, brand, sale_price, market_price, type, rating, description`) |
| Coverage | 11 categories · 90 sub-categories · 426 product types |
| Description | median 62 words (75% under 95 words, max 734) |

**Cleaning** (`src/ingest.py`): trimmed whitespace; dropped rows with missing product name
or description (or descriptions under 20 characters); filled missing brand with "Unbranded";
removed exact duplicates (same product, brand, prices and description). Same-name products
with different prices are kept because they are usually different pack sizes. Added a derived
`discount_pct` column.

**Assumptions / limitations:** the data is a snapshot, so prices may be out of date. There are
no pack-size, stock, delivery, offer or return-policy fields, so the bot treats those questions
as unsupported. About 31% of products have no rating and are shown as "Not rated".

## Pipeline
```
CSV ──► clean ──► one document per product ──► chunk long descriptions
                    (header + description)        (800 chars, 100 overlap)
                                                         │
                                       FastEmbed all-MiniLM-L6-v2 (384-d)
                                                         │
                        FAISS (inner product = cosine) + BM25 keyword index
                                                         │
   question ──► price filter parse ──► hybrid retrieval (RRF fusion) ──► top-k chunks
                                                         │
                         relevance gate ── below threshold ──► "not in catalogue" fallback
                                                         │
                       grounded prompt + context ──► OpenRouter LLM ──► answer + sources
```

1. **Data**: the cleaned CSV is saved to `data/processed/products_clean.csv`.
2. **Chunking**: **record-based**. Each product becomes one document: a structured header
   (product, brand, category path, price/MRP/discount, rating) followed by the description.
   Most descriptions are short (median 62 words), so splitting them would separate facts from the
   product they describe. Only descriptions longer than **800 characters** are split with
   `RecursiveCharacterTextSplitter`, with **100 characters of overlap** so a sentence cut at the
   boundary is still found. Every piece repeats the product header so it stays self-contained.
3. **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` through FastEmbed (ONNX, CPU, free,
   no API key). 384-dim normalised vectors, 256-token limit (fits our 800-char chunks). We first
   tried `bge-small-en-v1.5`, but on our CPU it embedded only ~5 docs/s (~95 min for the catalogue);
   MiniLM is ~20× faster with comparable retrieval quality for short product text.
4. **Vector store**: **FAISS** (`MAX_INNER_PRODUCT`, so scores are cosine similarity), saved to
   `vectorstore/faiss_index` and loaded at startup. All metadata (price, brand, rating…) is
   kept on each chunk.
5. **Retrieval (Hybrid RAG)**: we fetch 40 candidates from **FAISS** (semantic: "healthy breakfast" →
   oats) and 40 from **BM25** (keyword: exact brands such as "Saffola", "Yippee"), then merge the
   two lists with **Reciprocal Rank Fusion**, `score = Σ 1/(60 + rank)`. Price phrases such as
   "under ₹150" or "between 100 and 300" are parsed and used to **filter by metadata**, because
   vector search cannot compare numbers. The top-k (default 6) chunks go to the LLM.
6. **LLM + context**: an OpenRouter model (default `google/gemma-4-26b-a4b-it:free`, with a fallback
   chain for rate limits) at temperature 0. The system prompt tells it to answer only from the
   context, name the products, and never invent ratings or services.
7. **Answer + fallback**: there are two layers. (a) If the best semantic similarity is below **0.60**,
   the bot returns a fixed "not in the catalogue" message **without calling the LLM**. (b) Otherwise
   the prompt tells the LLM to say when the context is insufficient, or which part of a
   multi-part question it cannot answer. The UI shows the source chunks under every answer.

## Project structure
```
app.py              Streamlit chat UI
evaluate.py         Test questions → docs/evaluation.md
src/config.py       All settings (chunk size, k, threshold, models)
src/ingest.py       Clean → chunk → embed → FAISS
src/embeddings.py   Embedding model (shared by ingest + query)
src/rag.py          Hybrid retrieval, price filter, fallback, LLM chain
data/raw/           Original Kaggle CSV
vectorstore/        Saved FAISS index
```

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env          # add your OpenRouter key (free at openrouter.ai/keys)
python -m src.ingest          # only needed if vectorstore/faiss_index is missing
streamlit run app.py
```
