"""Pick one Unsplash photo per image concept and save hotlink + attribution to static/photos.json.

Follows the Unsplash API guidelines: photos are hotlinked (not re-hosted), the download
endpoint is triggered for every photo we use, and photographer + Unsplash are credited.

    UNSPLASH_ACCESS_KEY=... python -m scripts.fetch_photos

Resumable: concepts already in static/photos.json are skipped. Waits when the hourly
rate limit (50/hour for a new app) is used up.
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from src.images import codepoint, emoji_for

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "photos.json"
API = "https://api.unsplash.com"
APP = "basketbuddy_student_rag"  # utm_source for attribution links

# Image concept (emoji) -> photo search phrase. Must-match words are checked against the
# photo's description so e.g. "onion" doesn't return a garlic photo.
QUERIES = {
    "🧴": "skincare products", "🌸": "perfume bottle", "🌿": "herbs leaves", "🌶️": "indian spices",
    "🥛": "milk bottle", "🥣": "breakfast cereal bowl", "🫙": "pickle jar", "🧼": "soap bar",
    "🥜": "mixed nuts", "🍪": "cookies", "🍫": "chocolate bar", "🥨": "indian namkeen snack",
    "🧽": "cleaning sponge", "☕": "coffee cup", "🌾": "flour bowl", "🫖": "tea pot",
    "🍶": "glass bottle", "🧀": "cheese block", "🍵": "tea cup", "🍬": "candy sweets",
    "🧺": "laundry detergent", "🕯️": "candles", "🍚": "basmati rice", "🍽️": "dinner plate",
    "🪥": "toothbrush", "🫘": "lentils", "💆": "hair oil", "🧷": "baby diapers",
    "🍱": "lunch box", "🐕": "dog food", "💪": "protein powder", "🪒": "razor",
    "🫐": "blueberries", "🧁": "cupcake", "🍲": "cooking pot", "🧃": "fruit juice",
    "🫒": "olive oil", "🥄": "kitchen utensils", "🚿": "shower gel", "🍓": "strawberry jam",
    "💇": "hair color", "🍳": "frying pan", "🪔": "incense sticks", "🍗": "chicken",
    "🩸": "sanitary pads", "🍜": "noodles", "🫗": "cooking oil", "🍟": "potato chips",
    "🥥": "coconut", "🧻": "paper towels", "🍝": "pasta", "🥢": "soy sauce",
    "🧈": "butter", "🍛": "indian curry", "🍯": "honey", "🧹": "broom",
    "🎂": "cake decorating", "✏️": "pencils", "📒": "notebooks", "🧂": "salt",
    "🚽": "toilet cleaner", "🥬": "leafy greens", "🍅": "tomatoes", "😷": "face mask",
    "🗑️": "trash bin", "🫓": "papad", "🔪": "kitchen knife", "🌮": "nachos",
    "💄": "lipstick", "🪣": "bucket", "💊": "medicine tablets", "🍨": "ice cream",
    "🥟": "samosa", "👕": "clothes hanger", "💅": "nail polish", "🧔": "beard oil",
    "🍘": "crackers", "🐟": "fresh fish", "🍼": "baby bottle", "🛁": "bath salts",
    "🦟": "mosquito repellent", "💡": "led bulb", "🍞": "bread loaf", "🎁": "gift box",
    "🔋": "batteries", "🥤": "soft drink", "🍭": "lollipop", "✂️": "scissors",
    "🥙": "hummus dip", "👁️": "eye drops", "🐈": "cat grooming", "🥗": "salad",
    "❤️": "wellness", "🥓": "sausages", "🥭": "mango", "🍴": "cutlery",
    "🍎": "apples", "💧": "water bottle", "🪳": "insect spray", "🥦": "broccoli",
    "🍹": "mocktail", "🍊": "oranges", "🥚": "eggs", "🥕": "carrots", "🍿": "popcorn",
    "🫚": "ginger root", "🧮": "calculator", "🦐": "prawns", "🧄": "garlic",
    "🪝": "wall hooks", "🌱": "seedling", "🚗": "car cleaning", "🦻": "cotton buds",
    "🍮": "pudding dessert", "🦮": "dog leash", "🍋": "lemons", "☂️": "umbrella",
    "🥪": "mayonnaise", "🩹": "bandage", "🖍️": "crayons", "🔥": "gas stove",
    "🫛": "green peas", "🍖": "mutton", "🌽": "corn", "🍌": "bananas",
    "🥫": "canned food", "🍑": "peaches", "🧅": "onion", "🤰": "pregnancy",
    "🪴": "plant pot", "🎾": "dog toy", "🥖": "baguette", "🌹": "roses",
    "🔌": "charger cable", "👞": "shoe polish", "🥝": "kiwi fruit", "🎈": "balloons",
    "🎉": "party decorations", "🍆": "eggplant", "🫑": "bell pepper", "🥐": "croissant",
    "🥒": "cucumber", "🍍": "pineapple", "🍰": "slice of cake", "🍉": "watermelon",
    "🍷": "wine glass", "👶": "baby bib", "🥔": "potatoes", "🎃": "pumpkin",
    "🥑": "avocado", "🍇": "grapes", "🔔": "puja thali", "🍣": "sushi rice",
    "🍐": "pears", "🌭": "hot dog sausage", "🍕": "pizza base", "🪮": "hair comb",
    "🦀": "crab", "📚": "books", "🥯": "bagel", "🍄": "mushrooms", "🧸": "teddy bear",
    "⚖️": "weighing scale", "💐": "flower bouquet", "🎨": "holi colours",
    "🌻": "sunflower oil", "🍒": "cherries", "🧋": "iced tea", "🍈": "melon",
}


def concepts_by_usage() -> list[str]:
    import pandas as pd

    df = pd.read_csv(ROOT / "data" / "processed" / "products_clean.csv")
    c = Counter(emoji_for(r.product, r.category, r.type) for r in df.itertuples())
    from src.images import CATEGORY_EMOJI

    for e in CATEGORY_EMOJI.values():
        c.setdefault(e, 0)
    return [e for e, _ in c.most_common()]


def call(session, url, **params):
    while True:
        r = session.get(url, params=params, timeout=30)
        if r.status_code == 403 and "Rate Limit" in r.text or r.status_code == 429:
            print("  rate limited; sleeping 5 min", flush=True)
            time.sleep(300)
            continue
        r.raise_for_status()
        remaining = int(r.headers.get("X-Ratelimit-Remaining", "1"))
        if remaining <= 0:
            print("  hourly limit used; sleeping 10 min and retrying", flush=True)
            time.sleep(600)
        return r


def pick(results, query):
    """Prefer a photo whose description mentions every query word, then the main noun."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2]

    def text(p):
        return " ".join(filter(None, [p.get("alt_description"), p.get("description"),
                                      p.get("slug", "").replace("-", " ")])).lower()

    def has(p, w):
        return w.rstrip("s") in text(p)

    for p in results:
        if words and all(has(p, w) for w in words):
            return p
    for p in results:
        if words and has(p, words[-1]):
            return p
    return results[0] if results else None


def main():
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        sys.exit("Set UNSPLASH_ACCESS_KEY")
    s = requests.Session()
    s.headers.update({"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [e for e in concepts_by_usage() if f"{codepoint(e)}" not in data and e in QUERIES]
    print(f"{len(data)} done, {len(todo)} to fetch", flush=True)
    for e in todo:
        q = QUERIES[e]
        r = call(s, f"{API}/search/photos", query=q, per_page=10, content_filter="high", orientation="squarish")
        p = pick(r.json().get("results", []), q)
        if not p:
            print(f"  {e} {q!r}: no result", flush=True)
            continue
        call(s, p["links"]["download_location"])  # required by the API guidelines
        utm = f"utm_source={APP}&utm_medium=referral"
        data[codepoint(e)] = {
            "emoji": e, "query": q, "id": p["id"],
            "url": p["urls"]["raw"] + "&w=400&h=400&fit=crop&crop=entropy&q=70&auto=format",
            "alt": p.get("alt_description") or q,
            "author": p["user"]["name"], "author_url": f"{p['user']['links']['html']}?{utm}",
            "photo_url": f"{p['links']['html']}?{utm}", "unsplash_url": f"https://unsplash.com/?{utm}",
        }
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {e} {q!r} -> {p['id']} by {p['user']['name']} ({len(data)} total)", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
