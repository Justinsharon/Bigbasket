# BigBasket Product Assistant — RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers shopper questions about
BigBasket's grocery catalogue (products, brands, prices, ratings, descriptions),
grounded only in the dataset.

## Dataset
- **Source:** Kaggle — *BigBasket Entire Product List (~28K datapoints)*
- **License:** CC BY-NC-SA 4.0 (non-commercial, attribution, share-alike)
- Place the CSV in `data/raw/`.

## Stack
LangChain · FAISS · FastEmbed (BAAI/bge-small-en-v1.5) · BM25 (hybrid) · OpenRouter LLM · Streamlit

## Pipeline
_To be finalised: data → chunking → embeddings → vector store → retrieval → LLM/context → answer._

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # add your OpenRouter key
streamlit run app.py
```
