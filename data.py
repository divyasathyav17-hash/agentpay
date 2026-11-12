import random, re

FX = {"INR": 1.0, "USD": 83.5, "GBP": 105.0, "AED": 22.7, "SGD": 62.0}   # sample rates
DUTY = {"IN": 0.0, "US": 0.28, "UK": 0.28, "AE": 0.25, "SG": 0.27}      # estimated duty + tax

# ADD A NEW PRODUCT = ADD ONE LINE HERE:
# (name, search keywords, India price in INR, intl_ratio)
# intl_ratio = price abroad (converted to INR) / India price, before fees and duty.
#   about 0.66 or lower -> buying abroad wins   |   about 0.78 or higher -> India wins
PRODUCTS = [
    ("Sony WH-1000XM5", "headphones headphone sony noise cancelling wireless", 41990, 0.66),
    ("iPhone 15 (128GB)", "iphone apple phone smartphone mobile", 69900, 0.80),
    ("Apple AirPods Pro 2", "airpods apple earbuds earphones headphones wireless", 24900, 0.68),
    ("Samsung Galaxy S24", "samsung galaxy phone smartphone mobile s24", 74999, 0.82),
    ("MacBook Air M2", "macbook apple laptop computer notebook air m2", 99900, 0.83),
    ("Dell XPS 13", "dell xps laptop computer notebook", 119990, 0.66),
    ("PlayStation 5", "playstation ps5 sony console gaming game", 49990, 0.80),
    ("Nintendo Switch OLED", "nintendo switch console gaming game", 31999, 0.70),
    ("Apple Watch Series 9", "apple watch smartwatch series 9", 41900, 0.78),
    ("Kindle Paperwhite", "kindle amazon ebook reader books", 16999, 0.65),
    ("GoPro Hero 12", "gopro hero camera action", 39990, 0.66),
    ("Canon EOS R50", "canon eos camera mirrorless dslr", 69995, 0.64),
    ("Nike Air Zoom Pegasus", "nike shoes running sneakers footwear", 11995, 0.60),
    ("Adidas Ultraboost", "adidas shoes running sneakers footwear ultraboost", 17999, 0.62),
    ("Ray-Ban Wayfarer", "rayban ray-ban sunglasses glasses wayfarer", 9990, 0.58),
    ("Logitech MX Master 3S", "logitech mouse mx master wireless computer", 9995, 0.64),
    ("JBL Flip 6", "jbl speaker bluetooth portable flip", 9999, 0.66),
    ("Bose QuietComfort Ultra", "bose headphones headphone noise cancelling quietcomfort", 35900, 0.63),
]
SCAM = {"Sony WH-1000XM5": "SG"}                    # demo: suspiciously cheap, brand-new seller
SLOPE = {("iPhone 15 (128GB)", "IN"): -0.012}       # demo: India price slowly falling

CUR = {"IN": "INR", "US": "USD", "UK": "GBP", "AE": "AED", "SG": "SGD"}
SHIP_INR = {"IN": 0, "US": 1700, "UK": 1600, "AE": 700, "SG": 1100}
DAYS = {"IN": 2, "US": 9, "UK": 8, "AE": 5, "SG": 6}
VAR = {"IN": 1.0, "US": 1.0, "UK": 1.02, "AE": 0.97, "SG": 1.04}

ALIAS = {p[0]: " ".join(re.findall(r"[a-z0-9\-]+", (p[0] + " " + p[1]).lower())) for p in PRODUCTS}


def _sellers(name, india, ratio):
    out = []
    for c in CUR:
        r = random.Random(name + c)
        cur = CUR[c]
        if SCAM.get(name) == c:
            price, rt, rv, age, war = india * 0.45 / FX[cur], 4.9, 12, 2, 3
        elif c == "IN":
            price, rt, rv, age, war = india, round(r.uniform(4.3, 4.7), 1), r.randint(3000, 15000), r.randint(48, 100), 12
        else:
            price = india * ratio * VAR[c] / FX[cur]
            rt, rv, age, war = round(r.uniform(4.2, 4.8), 1), r.randint(800, 20000), r.randint(30, 100), r.choice([12, 12, 24])
        price = round(price)
        ship = round(SHIP_INR[c] / FX[cur])
        days = DAYS[c] + (r.randint(0, 2) if c != "IN" else 0)
        slope = SLOPE.get((name, c), 0)
        hist = [round(price * (1 + slope * (k - 5) + r.uniform(-0.008, 0.008)), 2) for k in range(6)]
        hist[5] = price
        out.append(dict(country=c, price=price, currency=cur, shipping=ship, days=days, rating=rt, reviews=rv,
                        age=age, warranty=war, history=hist, base=price,
                        platform=pick_platform(name, c, SCAM.get(name) == c)))
    return out


def build_catalogue():
    return {p[0]: _sellers(p[0], p[2], p[3]) for p in PRODUCTS}


EST = set()      # products created on the fly from a search (AI-estimated prices)


def add_product(cat, name, keywords, india, ratio):
    PRODUCTS.append((name, keywords, india, ratio))
    ALIAS[name] = " ".join(re.findall(r"[a-z0-9\-]+", (name + " " + keywords).lower()))
    cat[name] = _sellers(name, india, ratio)
    EST.add(name)
    return name


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


_EMOJI = [("headphone", "🎧"), ("phone", "📱"), ("laptop", "💻"), ("console", "🎮"), ("watch", "⌚"),
          ("kindle", "📖"), ("camera", "📷"), ("shoes", "👟"), ("sunglasses", "🕶️"), ("mouse", "🖱️"), ("speaker", "🔊")]


def emoji(name):
    words = ALIAS[name].split()
    return next((e for k, e in _EMOJI if any(k in w for w in words)), "🛍️")


# (name, kind, trust 0-100, website). Illustrative trust scores for the prototype.
PLATFORMS = {
    "IN": [("Amazon.in", "online", 92, "amazon.in"), ("Flipkart", "online", 90, "flipkart.com"),
           ("Croma", "showroom", 95, "croma.com"), ("Reliance Digital", "showroom", 94, "reliancedigital.in"),
           ("Vijay Sales", "showroom", 90, "vijaysales.com")],
    "US": [("Amazon.com", "online", 92, "amazon.com"), ("Best Buy", "showroom", 95, "bestbuy.com"),
           ("Walmart", "online", 93, "walmart.com"), ("B&H Photo", "showroom", 95, "bhphotovideo.com"),
           ("Newegg", "online", 85, "newegg.com")],
    "UK": [("Currys", "showroom", 94, "currys.co.uk"), ("Argos", "showroom", 92, "argos.co.uk"),
           ("Amazon.co.uk", "online", 92, "amazon.co.uk"), ("John Lewis", "showroom", 96, "johnlewis.com"),
           ("AO.com", "online", 90, "ao.com")],
    "AE": [("Amazon.ae", "online", 90, "amazon.ae"), ("Noon", "online", 88, "noon.com"),
           ("Sharaf DG", "showroom", 93, "sharafdg.com"), ("Jumbo Electronics", "showroom", 94, "jumbo.ae")],
    "SG": [("Challenger", "showroom", 93, "challenger.sg"), ("Lazada", "online", 84, "lazada.sg"),
           ("Shopee", "online", 82, "shopee.sg"), ("Courts", "showroom", 90, "courts.com.sg"),
           ("Harvey Norman", "showroom", 92, "harveynorman.com.sg")],
}


def pick_platform(name, country, scam=False):
    if scam:
        return {"name": "QuickDeal (unverified)", "kind": "online", "trust": 18, "url": None, "link": None}
    pool = PLATFORMS[country]
    if emoji(name) in ("👟", "🕶️"):                       # fashion sells on online stores
        pool = [p for p in pool if p[1] == "online"]
    n, k, t, u = random.Random("plat" + name + country).choice(pool)
    return {"name": n, "kind": k, "trust": t, "url": u, "link": store_link(n, u, name)}


LINKS = {   # opens the platform's own search results for the product
    "Amazon.in": "https://www.amazon.in/s?k={q}", "Flipkart": "https://www.flipkart.com/search?q={q}",
    "Croma": "https://www.croma.com/searchB?q={q}", "Reliance Digital": "https://www.reliancedigital.in/search?q={q}",
    "Vijay Sales": "https://www.vijaysales.com/search/{q}", "Amazon.com": "https://www.amazon.com/s?k={q}",
    "Best Buy": "https://www.bestbuy.com/site/searchpage.jsp?st={q}", "Walmart": "https://www.walmart.com/search?q={q}",
    "B&H Photo": "https://www.bhphotovideo.com/c/search?q={q}", "Newegg": "https://www.newegg.com/p/pl?d={q}",
    "Currys": "https://www.currys.co.uk/search?q={q}", "Argos": "https://www.argos.co.uk/search/{q}/",
    "Amazon.co.uk": "https://www.amazon.co.uk/s?k={q}", "John Lewis": "https://www.johnlewis.com/search?search-term={q}",
    "Amazon.ae": "https://www.amazon.ae/s?k={q}", "Noon": "https://www.noon.com/uae-en/search/?q={q}",
    "Sharaf DG": "https://uae.sharafdg.com/?q={q}&post_type=product", "Lazada": "https://www.lazada.sg/catalog/?q={q}",
    "Shopee": "https://shopee.sg/search?keyword={q}",
}


def store_link(platform, domain, product):
    from urllib.parse import quote_plus
    q = quote_plus(product)
    if platform in LINKS:
        return LINKS[platform].format(q=q)
    return f"https://www.google.com/search?q={q}+site%3A{domain}"      # fallback for stores without a known search URL