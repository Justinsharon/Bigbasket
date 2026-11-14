"""Run the test questions and write an evaluation report.

    python evaluate.py            # writes docs/evaluation.md
"""
import time
from pathlib import Path

from src.rag import BigBasketRAG

# (type, question, keywords that should appear in retrieved evidence; None = should fall back)
TESTS = [
    ("Factual", "What is the price of Saffola Gold oil?", ["saffola"]),
    ("Factual", "What is Himalaya Neem Face Wash used for?", ["himalaya", "neem"]),
    ("Comparison", "Compare Tata Tea and Red Label tea on price and rating", ["tata", "red label"]),
    ("Comparison", "Which is cheaper: Maggi noodles or Yippee noodles?", ["maggi", "yippee"]),
    ("Multi-part", "Suggest a gluten-free snack under ₹150 and tell me its brand and rating", ["gluten"]),
    ("Multi-part", "Which baby diapers are available and which one has the highest discount?", ["diaper"]),
    ("Semantic", "Something healthy for breakfast with oats", ["oat"]),
    ("Unsupported", "Do you deliver to Pune within 10 minutes?", None),
    ("Unsupported", "What is BigBasket's return and refund policy?", None),
    ("Unsupported", "Who won the cricket world cup in 2011?", None),
]


def evidence_hit(docs, keywords):
    text = " ".join(d.page_content.lower() for d in docs)
    return all(k in text for k in keywords)


def main():
    rag = BigBasketRAG()
    rows = []
    for qtype, q, kws in TESTS:
        out = {}
        for mode in ("vector", "hybrid"):
            docs, best, _ = rag.retrieve(q, mode)
            out[mode] = (evidence_hit(docs, kws) if kws else None, best, docs)
        res = rag.answer(q, "hybrid")
        rows.append((qtype, q, kws, out, res))
        print(f"[{qtype}] {q}\n  best={res.best_score:.3f} fallback={res.used_fallback}\n  {res.answer[:300]}\n")
        time.sleep(2)  # be gentle with free-tier rate limits

    lines = ["# Evaluation report", "",
             "| # | Type | Question | Best sim. | Evidence (vector) | Evidence (hybrid) | Fell back? |",
             "|---|---|---|---|---|---|---|"]
    fmt = lambda v: "n/a" if v is None else ("✅" if v else "❌")
    for i, (t, q, kws, out, res) in enumerate(rows, 1):
        lines.append(f"| {i} | {t} | {q} | {res.best_score:.2f} | {fmt(out['vector'][0])} | "
                     f"{fmt(out['hybrid'][0])} | {'yes' if res.used_fallback else 'no'} |")
    lines += ["", "## Answers", ""]
    for i, (t, q, kws, out, res) in enumerate(rows, 1):
        top = ", ".join(f"{d.metadata['product']} ({d.metadata['brand']})" for d in out["hybrid"][2][:3])
        lines += [f"### {i}. {q}", f"*Type:* {t} · *Top retrieved:* {top}", "", res.answer, ""]
    Path("docs").mkdir(exist_ok=True)
    Path("docs/evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote docs/evaluation.md")


if __name__ == "__main__":
    main()
