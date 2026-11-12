import os, re, math, time, json, random, requests
from datetime import datetime
import numpy as np
from flask import Flask, jsonify, request, send_from_directory, redirect
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest
from data import build_catalogue, FX, DUTY, ALIAS, slug, emoji, add_product, EST
from smart import estimate, unknown_words
from live import live_sellers, LIVE_IMG, LIVE_TIME, LIVE_META

load_dotenv()
app = Flask(__name__, static_folder="static", static_url_path="")
CAT = build_catalogue()
PP = "https://api-m.sandbox.paypal.com"
CID, SEC = os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")
FX_FEE = 0.035
TX_FILE = "transactions.json"
TX = json.load(open(TX_FILE)) if os.path.exists(TX_FILE) else []
PENDING, WATCH, RECENT = {}, {}, []


# ---------- 2. Landed cost ----------
def landed(s):
    base = (s["price"] + s["shipping"]) * FX[s["currency"]]
    fee = base * FX_FEE if s["country"] != "IN" else 0
    duty = base * DUTY[s["country"]]
    return {"base": round(base), "fx_fee": round(fee), "duty": round(duty), "total": round(base + fee + duty)}


# ---------- 3. Seller trust score ----------
def trust(s, median_base):
    score = (s["rating"] / 5) * 40 + min(math.log10(s["reviews"] + 1) / 4, 1) * 30 + min(s["age"] / 48, 1) * 30
    flags = []
    if s["price"] * FX[s["currency"]] < 0.75 * median_base:
        score -= 25; flags.append("Price far below market")
    if s["reviews"] < 100: flags.append("Very few reviews")
    if s["age"] < 12: flags.append("New seller")
    score = max(0, min(100, round(score)))
    level = "Low risk" if score >= 75 else "Medium risk" if score >= 50 else "High risk"
    return {"score": score, "level": level, "flags": flags}


# ---------- 5. Price prediction (linear trend on price history) ----------
def trend(s):
    h = s["history"]; n = len(h); xs = range(n)
    mx, my = sum(xs) / n, sum(h) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, h)) / sum((x - mx) ** 2 for x in xs)
    return round((slope * 2) / h[-1] * 100, 1)   # expected % change over next 2 periods


# ---------- 4. Buy / don't buy ----------
def verdict(rows):
    local = next(r for r in rows if r["country"] == "IN")
    ok = [r for r in rows if r["trust"]["level"] != "High risk" and not r["late"] and not r["over_budget"]]
    warn = f"Cheapest offer ({rows[0]['country']}) skipped because of high seller risk." \
        if rows[0]["trust"]["level"] == "High risk" else ""
    if not ok:
        return {"decision": "NO_MATCH", "reason": "No safe seller fits your budget and delivery limit.", "warn": warn, "best_country": None}
    best = ok[0]
    saving = local["landed"]["total"] - best["landed"]["total"]
    if best["country"] == "IN" or saving < 0.08 * local["landed"]["total"]:
        d, why = "BUY_LOCAL", "Buying locally is as cheap or cheaper once duty and fees are added, and it arrives faster."
        best = local
    elif best["trend_pct"] < -1.5:
        d, why = "WAIT", f"{best['country']} price is trending down ({best['trend_pct']}%). Waiting may save more."
    else:
        d, why = "BUY_INTERNATIONAL", f"Buying from {best['country']} saves about ₹{saving:,} versus India, even after duty and fees."
    return {"decision": d, "reason": why, "warn": warn, "best_country": best["country"], "saving": max(saving, 0)}


def analyse(prod, max_days=30, budget=None, sellers=None):
    sellers = sellers or CAT[prod]
    bases = sorted(s["price"] * FX[s["currency"]] for s in sellers)
    med = bases[len(bases) // 2]
    rows = []
    for s in sellers:
        l = landed(s)
        rows.append({**{k: s[k] for k in ("country", "price", "currency", "shipping", "days", "warranty", "rating", "reviews", "platform")},
                     "landed": l, "trust": trust(s, med), "trend_pct": trend(s),
                     "late": s["days"] > max_days, "over_budget": bool(budget and l["total"] > budget)})
    rows.sort(key=lambda r: r["landed"]["total"])
    return {"product": prod, "slug": slug(prod), "emoji": emoji(prod), "estimated": prod in EST, "max_days": max_days, "budget": budget, "rows": rows, "verdict": verdict(rows)}


# ---------- 1. Natural language discovery ----------
def parse(q):
    ql = q.lower()
    words = re.findall(r"[a-z0-9\-]+", ql)
    score = {p: sum(w in ALIAS[p].split() for w in words) for p in CAT}
    prod = max(score, key=score.get)
    if score[prod] == 0: prod = None
    d = re.search(r"(\d+)\s*(?:days?|naal)", ql)
    b = re.search(r"(?:under|below|budget|max)\s*(?:rs\.?|inr|₹)?\s*([\d,]+)", ql)
    budget = int(b.group(1).replace(",", "")) if b else None
    if budget and budget < 1000: budget = None
    return prod, int(d.group(1)) if d else 30, budget


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/api/config")
def config():
    return jsonify(client_id=CID or "", has_live=bool(os.getenv("SERPAPI_KEY")))          # PayPal Client ID is public, so no edit in index.html is needed


@app.route("/api/live-tick", methods=["POST"])     # demo: simulated live price movement (+/-0.6% per tick, max +/-6%)
def live_tick():
    for s in CAT[request.json["product"]]:
        p = s["price"] * (1 + random.uniform(-0.006, 0.006))
        s["price"] = round(min(max(p, s["base"] * 0.94), s["base"] * 1.06), 2)
    return jsonify(ok=True)


@app.route("/img/<slug_name>")        # local file first (static/images), else auto-fetch a picture and cache it
def product_img(slug_name):
    folder = os.path.join(app.static_folder, "images")
    os.makedirs(folder, exist_ok=True)
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.exists(os.path.join(folder, f"{slug_name}.{ext}")):
            return send_from_directory(folder, f"{slug_name}.{ext}")
    if slug_name in LIVE_IMG:
        return redirect(LIVE_IMG[slug_name])
    name = next((n for n in CAT if slug(n) == slug_name), None)
    try:
        ua = {"User-Agent": "AgentPayHackathon/1.0 (student project)"}
        r = requests.get("https://en.wikipedia.org/w/api.php", headers=ua, timeout=8, params={
            "action": "query", "generator": "search", "gsrsearch": name, "gsrlimit": 1, "prop": "pageimages",
            "piprop": "thumbnail", "pithumbsize": 500, "format": "json"})
        page = next(iter(r.json().get("query", {}).get("pages", {}).values()))
        img = requests.get(page["thumbnail"]["source"], headers=ua, timeout=10)
        ext = "png" if "png" in img.headers.get("content-type", "") else "jpg"
        open(os.path.join(folder, f"{slug_name}.{ext}"), "wb").write(img.content)
        return send_from_directory(folder, f"{slug_name}.{ext}")
    except Exception:
        return "", 404


@app.route("/api/products")
def products():
    return jsonify([{"name": n, "slug": slug(n), "emoji": emoji(n)} for n in CAT])


@app.route("/api/search")
def search():
    q = request.args.get("q", "")
    prod, days, budget = parse(q)
    if not prod or unknown_words(q, ALIAS):          # product not in the catalogue: let AI estimate it
        est = estimate(q)
        if est:
            prod = est["name"] if est["name"] in CAT else add_product(CAT, est["name"], est["keywords"], est["india_price_inr"], est["intl_ratio"])
    if not prod:
        return jsonify(error="No matching product. Try: Sony headphones under 40000, or iPhone 15 within 10 days"), 404
    real = request.args.get("real", "1" if os.getenv("SERPAPI_KEY") else "0") == "1"
    if real:                                             # REAL mode: never mixes in demo numbers
        got = live_sellers(prod, force=request.args.get("refresh") == "1")
        if not got:
            return jsonify(error="Real prices are not available for this product right now (no store results, quota used, or SERPAPI_KEY missing). Untick 'Use real prices' to see demo data."), 502
        res = analyse(prod, days, budget, sellers=got)
        res["live"] = True
        res["checked_at"] = LIVE_TIME.get(prod)
        return jsonify(res)
    res = analyse(prod, days, budget)
    res["live"] = False
    return jsonify(res)


# ---------- 7. Fraud detection (Isolation Forest + rules) ----------
_r = np.random.RandomState(1)
_X = np.c_[_r.normal(40000, 15000, 500).clip(1000), _r.normal(75, 12, 500).clip(20, 100),
           _r.binomial(1, .4, 500), _r.randint(8, 23, 500), _r.poisson(1, 500)]
FRAUD = IsolationForest(contamination=0.03, random_state=1).fit(_X)


def risk_check(total, trust_score, intl):
    recent = sum(1 for t in RECENT if time.time() - t < 3600)
    anomaly = FRAUD.predict([[total, trust_score, int(intl), datetime.now().hour, recent]])[0] == -1
    reasons = []
    if anomaly: reasons.append("Unusual transaction pattern (ML anomaly model)")
    if trust_score < 50: reasons.append("Seller has a high risk score")
    if recent >= 3: reasons.append("Many orders in the last hour")
    if total > 150000: reasons.append("Very high order value")
    level = "HIGH" if len(reasons) >= 2 else "MEDIUM" if reasons else "LOW"
    return {"level": level, "reasons": reasons}


# ---------- 6. PayPal checkout + history ----------
def pp_token():
    r = requests.post(f"{PP}/v1/oauth2/token", auth=(CID, SEC), data={"grant_type": "client_credentials"})
    return r.json()["access_token"]


@app.route("/api/orders", methods=["POST"])
def create_order():
    b = request.json
    sellers = live_sellers(b["product"]) if b.get("real") else None      # cached, no new API call
    row = next(r for r in analyse(b["product"], sellers=sellers)["rows"] if r["country"] == b["country"])
    total = row["landed"]["total"]                      # price is recomputed on the server
    risk = risk_check(total, row["trust"]["score"], row["country"] != "IN")
    if risk["level"] == "HIGH":
        return jsonify(blocked=True, **risk), 403
    if not CID:
        return jsonify(error="PayPal keys missing in .env"), 500
    usd = round(total / FX["USD"], 2)
    r = requests.post(f"{PP}/v2/checkout/orders", headers={"Authorization": f"Bearer {pp_token()}"},
                      json={"intent": "CAPTURE", "purchase_units": [{"description": b["product"],
                            "amount": {"currency_code": "USD", "value": f"{usd:.2f}"}}]})
    oid = r.json()["id"]
    PENDING[oid] = {"product": b["product"], "country": b["country"], "total_inr": total, "risk": risk["level"]}
    return jsonify(id=oid)


@app.route("/api/orders/<oid>/capture", methods=["POST"])
def capture(oid):
    r = requests.post(f"{PP}/v2/checkout/orders/{oid}/capture",
                      headers={"Authorization": f"Bearer {pp_token()}", "Content-Type": "application/json"})
    info = PENDING.get(oid, {})
    TX.insert(0, {"id": oid, "status": r.json().get("status"), "time": datetime.now().strftime("%d %b %H:%M"), **info})
    json.dump(TX, open(TX_FILE, "w"))
    if r.json().get("status") == "COMPLETED":
        RECENT.append(time.time())
    return jsonify(r.json())


@app.route("/api/transactions")
def transactions():
    return jsonify(TX)


# ---------- 8. Price drop alerts ----------
def best_safe(prod):
    return [r for r in analyse(prod)["rows"] if r["trust"]["level"] != "High risk"][0]


@app.route("/api/watch", methods=["POST"])
def watch():
    p = request.json["product"]
    WATCH[p] = best_safe(p)["landed"]["total"]
    return jsonify(ok=True, baseline=WATCH[p])


@app.route("/api/alerts")
def alerts():
    out = []
    for p, base in WATCH.items():
        b = best_safe(p); now = b["landed"]["total"]
        if now < base:
            out.append({"product": p, "old": base, "new": now, "drop": base - now, "country": b["country"]})
    return jsonify(out)


@app.route("/api/simulate-drop", methods=["POST"])       # demo helper: cuts the best seller's price by 8%
def simulate_drop():
    p = request.json["product"]; c = best_safe(p)["country"]
    for s in CAT[p]:
        if s["country"] == c: s["price"] = round(s["price"] * 0.92, 2)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True)