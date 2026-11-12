import os, re, json, requests

STOP = set("under below within days day budget max rs inr price buy best cheap cheapest for in the a an of and to me find "
           "naal show want need i with from my new latest".split())
# category word -> (typical India price in INR, intl_ratio) used when no LLM key is set
GUESS = {"laptop": (65000, .72), "phone": (30000, .80), "tv": (40000, .70), "television": (40000, .70),
         "camera": (50000, .66), "watch": (9000, .75), "headphone": (6000, .66), "headphones": (6000, .66),
         "earbuds": (4000, .68), "speaker": (5000, .68), "shoes": (6000, .60), "shoe": (6000, .60),
         "sneakers": (6000, .60), "bag": (3000, .60), "backpack": (3000, .60), "tablet": (30000, .75),
         "console": (40000, .78), "mouse": (1500, .64), "keyboard": (3000, .64), "monitor": (15000, .70),
         "printer": (9000, .70), "jacket": (4000, .60), "perfume": (3000, .65), "sunglasses": (5000, .58)}
PROMPT = ('A shopper searched for: "{q}". Reply with ONLY a JSON object: {{"name": proper product name, '
          '"keywords": lowercase search words separated by spaces, "india_price_inr": typical retail price in India as an integer, '
          '"intl_ratio": number between 0.55 and 0.90 (typical price abroad converted to INR divided by the India price, before duty)}}. '
          'If this is not a real purchasable consumer product, reply {{"error": "not a product"}}.')
_cache = {}


def clean_query(q):
    q = re.sub(r"(under|below|budget|max)\s*(rs\.?|inr|₹)?\s*[\d,]+", " ", q.lower())
    q = re.sub(r"(within\s*)?\d+\s*(days?|naal)", " ", q)
    return re.sub(r"\s+", " ", q).strip()


def unknown_words(q, alias):
    known = {w for a in alias.values() for w in re.findall(r"[a-z]+", a)}
    return [w for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 1 and w not in STOP and w not in known]


def _llm(q):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=20,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.getenv("LLM_MODEL", "claude-haiku-5-5"), "max_tokens": 300,
                                "messages": [{"role": "user", "content": PROMPT.format(q=q)}]})
        d = json.loads(re.search(r"\{.*\}", r.json()["content"][0]["text"], re.S).group(0))
        if "error" in d:
            return "reject"
        return {"name": str(d["name"])[:60], "keywords": str(d["keywords"]).lower(),
                "india_price_inr": max(200, min(int(d["india_price_inr"]), 500000)),
                "intl_ratio": max(0.55, min(float(d["intl_ratio"]), 0.9))}
    except Exception:
        return None


def estimate(q):
    """Return an estimated catalogue entry for a product that is not in data.py, or None."""
    q = clean_query(q)
    if len(q) < 3:
        return None
    if q in _cache:
        return _cache[q]
    res = _llm(q)
    if res == "reject":
        res = None
    elif res is None:
        hit = next((GUESS[w] for w in re.findall(r"[a-z]+", q) if w in GUESS), None)
        if hit:
            res = {"name": q.title()[:60], "keywords": q, "india_price_inr": hit[0], "intl_ratio": hit[1]}
    _cache[q] = res
    return res