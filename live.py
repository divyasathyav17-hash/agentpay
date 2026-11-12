"""Real prices from Google Shopping through SerpApi (needs SERPAPI_KEY in .env)."""
import os, re, math, json, time, requests
from concurrent.futures import ThreadPoolExecutor
from data import FX, CUR, SHIP_INR, DAYS, slug

GL = {"IN": "in", "US": "us", "UK": "gb", "AE": "ae", "SG": "sg"}   # SerpApi `gl` = country of the search
CACHE_FILE, TTL = "live_cache.json", 6 * 3600                       # refresh every 6h (free plan = 250 searches/month)
LIVE_TIME = {}                                                       # product -> when its prices were fetched
LIVE_IMG = {}                                                        # slug -> real product picture (thumbnail)
LIVE_META = {}                                                       # product -> time the prices were fetched
SHOWROOMS = ("croma", "reliance", "best buy", "currys", "argos", "john lewis", "sharaf", "jumbo", "challenger",
             "courts", "harvey norman", "b&h", "apple", "samsung", "sony")
TRUSTED = SHOWROOMS + ("amazon", "flipkart", "walmart", "noon", "lazada", "shopee", "newegg", "target", "ebay", "vijay")


def _load():
    try:
        return json.load(open(CACHE_FILE))
    except Exception:
        return {}


def _fetch(name, country, key):
    try:
        r = requests.get("https://serpapi.com/search.json", timeout=30,
                         params={"engine": "google_shopping", "q": name, "gl": GL[country], "hl": "en", "api_key": key}).json()
    except Exception as e:
        print("[live] request failed:", e); return None
    if r.get("error"):
        print("[live]", country, r["error"]); return None
    toks = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 1][:5]
    need = max(1, math.ceil(0.5 * len(toks)))                              # at least half of the name words must match
    items = [i for i in r.get("shopping_results", [])
             if i.get("extracted_price") and not i.get("second_hand_condition")
             and sum(t in i.get("title", "").lower() for t in toks) >= need]
    if not items:
        return None
    prices = sorted(i["extracted_price"] for i in items)
    med = prices[len(prices) // 2]
    items = [i for i in items if i["extracted_price"] >= 0.5 * med]      # drop cheap accessories
    b = min(items, key=lambda i: i["extracted_price"])
    return {"price": b["extracted_price"], "source": b.get("source", "Online store"), "rating": b.get("rating"),
            "reviews": b.get("reviews"), "link": b.get("link") or b.get("product_link"), "thumb": b.get("thumbnail")}


def live_sellers(name, force=False):
    """Seller list in the same shape as data._sellers(), or None if real prices are unavailable."""
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return None
    cache = _load()
    hit = cache.get(name)
    if hit and not force and time.time() - hit["t"] < TTL:
        data = hit["data"]; LIVE_TIME[name] = hit["t"]
    else:
        with ThreadPoolExecutor(5) as ex:
            res = list(ex.map(lambda c: _fetch(name, c, key), GL))
        data = {c: r for c, r in zip(GL, res) if r}
        LIVE_TIME[name] = time.time()
        cache[name] = {"t": LIVE_TIME[name], "data": data}
        json.dump(cache, open(CACHE_FILE, "w"))
    LIVE_META[name] = (cache.get(name) or {}).get("t", time.time())
    if "IN" not in data or len(data) < 2:
        return None
    out = []
    for c, r in data.items():
        cur, src = CUR[c], r["source"]
        low = src.lower()
        out.append(dict(
            country=c, price=r["price"], currency=cur, shipping=round(SHIP_INR[c] / FX[cur]),
            days=DAYS[c] + (1 if c != "IN" else 0), rating=r["rating"] or 4.0, reviews=r["reviews"] or 0,
            age=36, warranty=12, history=[r["price"]] * 6, base=r["price"],      # age, warranty, history = estimates
            platform={"name": src, "kind": "showroom" if any(k in low for k in SHOWROOMS) else "online",
                      "trust": 90 if any(k in low for k in TRUSTED) else 65, "url": None, "link": r["link"]}))
    thumb = next((data[c]["thumb"] for c in ("IN", "US", "UK", "AE", "SG") if c in data and data[c].get("thumb")), None)
    if thumb:
        LIVE_IMG[slug(name)] = thumb
    return out