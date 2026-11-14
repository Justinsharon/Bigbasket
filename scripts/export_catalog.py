"""Export a slim product catalogue for the storefront (static/catalog.json).

Built from the FAISS docstore so it always matches the index. Run after src.ingest:
    python -m scripts.export_catalog
"""
import json

from langchain_community.vectorstores import FAISS

from src import config
from src.embeddings import get_embeddings
from src.images import CATEGORY_EMOJI, image_for, image_path

FIELDS = ["id", "name", "brand", "cat", "sub", "type", "price", "mrp", "off", "rating", "img"]


def main():
    vs = FAISS.load_local(str(config.INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True)
    rows = []
    for d in vs.docstore._dict.values():
        m = d.metadata
        if m["chunk"] != 0:
            continue
        _, url = image_for(m)
        rows.append([m["product_id"], m["product"], m["brand"], m["category"], m["sub_category"], m["type"],
                     round(m["sale_price"], 2), round(m["market_price"], 2), int(m["discount_pct"]),
                     m["rating"], (url or "").rsplit("/", 1)[-1]])
    rows.sort(key=lambda r: r[0])
    out = config.ROOT / "static" / "catalog.json"
    cats = {c: (image_path(e) or "").rsplit("/", 1)[-1] for c, e in CATEGORY_EMOJI.items()}
    out.write_text(json.dumps({"fields": FIELDS, "rows": rows, "cats": cats}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"{len(rows)} products -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
