"""ADSP 32030 Assignment 4 — the shop dataset. Same seed for everyone, so everyone gets the same 250,000 orders.
   python gen_shop.py                 → writes data/*.jsonl  (customers 25,000 · products 2,000 · orders 250,000 · reviews 120,000)
   python gen_shop.py --load          → also loads them, as-is, into database shop_raw on $MDB_URI (insert_many, 1,000 per batch)
Shapes (raw, referenced): customers{_id, name, email, city, state, tier, signup_date}; products{_id, sku, name, category, brand,
price, description}; orders{_id, customer_id, order_date, status, items:[{product_id, qty, unit_price}], total};
reviews{_id, product_id, customer_id, rating, title, text, review_date}. Build YOUR design from these (Part 1)."""
import json, os, random, sys, datetime as dt
SEED = 32030; N_CUST, N_PROD, N_ORD, N_REV = 25_000, 2_000, 250_000, 120_000
rnd = random.Random(SEED)
CATS = {"Electronics": ["Wireless Earbuds", "Bluetooth Speaker", "USB-C Charger", "Smart Watch", "Laptop Stand", "Webcam"],
        "Home & Kitchen": ["Chef's Knife", "Coffee Grinder", "Air Fryer", "Cast Iron Skillet", "Blender", "Kettle"],
        "Sports & Outdoors": ["Yoga Mat", "Trail Running Shoes", "Water Bottle", "Camping Tent", "Bike Helmet", "Hiking Backpack"],
        "Books": ["Data Engineering Handbook", "Cookbook", "Mystery Novel", "Field Guide", "Travel Atlas", "Poetry Collection"],
        "Toys & Games": ["Board Game", "Puzzle 1000pc", "Building Blocks", "Remote Control Car", "Card Game", "Plush Toy"],
        "Beauty": ["Face Serum", "Sunscreen SPF 50", "Hair Dryer", "Shampoo", "Lip Balm", "Moisturizer"],
        "Office": ["Ergonomic Chair", "Desk Lamp", "Notebook Set", "Gel Pens", "Monitor Arm", "Paper Shredder"],
        "Pet Supplies": ["Dog Leash", "Cat Tree", "Pet Bed", "Chew Toy", "Litter Box", "Bird Feeder"]}
BRANDS = ["Northwind", "Acme", "Lakeshore", "Maroon & Co", "Hyde Park Goods", "Midway", "Pilsen Works", "Loop Labs", "Prairie", "Calumet"]
CITIES = [("Chicago", "IL"), ("Evanston", "IL"), ("Naperville", "IL"), ("Milwaukee", "WI"), ("Madison", "WI"), ("Detroit", "MI"),
          ("Indianapolis", "IN"), ("Minneapolis", "MN"), ("St. Louis", "MO"), ("Columbus", "OH"), ("Austin", "TX"), ("Denver", "CO"),
          ("Seattle", "WA"), ("New York", "NY"), ("Atlanta", "GA"), ("Boston", "MA")]
FIRST = ["Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Ivy", "Lucas", "Nora", "Omar", "Priya", "Jin", "Sofia", "Mateo", "Aisha", "Kai"]
LAST = ["Nguyen", "Smith", "Garcia", "Patel", "Kim", "Johnson", "Lopez", "Chen", "Okafor", "Rossi", "Kowalski", "Haddad", "Silva", "Brown"]
GOOD = ["works great", "battery lasts all day", "very comfortable", "excellent build quality", "fast shipping", "exactly as described",
        "easy to set up", "great value for the price", "my kids love it", "quiet and powerful", "would buy again", "sturdy and light"]
BAD = ["stopped working after a week", "battery dies quickly", "arrived damaged", "cheap plastic", "too small", "instructions were confusing",
       "returned it", "not as described", "the strap broke", "loud and slow", "customer service never answered", "leaks"]
TYPOS = {"battery": "batery", "comfortable": "comfortible", "quality": "qualty", "shipping": "shiping", "damaged": "damged"}
STATUS = [("delivered", 0.62), ("shipped", 0.18), ("processing", 0.08), ("cancelled", 0.07), ("returned", 0.05)]
def day(a, b): return a + dt.timedelta(days=rnd.randrange((b - a).days))
def pick_status():
    x = rnd.random(); acc = 0
    for s, p in STATUS:
        acc += p
        if x < acc: return s
    return STATUS[-1][0]
customers = [{"_id": i, "name": f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", "email": f"user{i}@example.com",
              **dict(zip(("city", "state"), rnd.choice(CITIES))), "tier": rnd.choices(["bronze", "silver", "gold"], [0.7, 0.22, 0.08])[0],
              "signup_date": day(dt.date(2021, 1, 1), dt.date(2025, 6, 30)).isoformat()} for i in range(1, N_CUST + 1)]
products = []
for i in range(1, N_PROD + 1):
    cat = rnd.choice(list(CATS)); base = rnd.choice(CATS[cat]); brand = rnd.choice(BRANDS)
    price = round(rnd.lognormvariate(3.3, 0.8), 2); price = max(4.99, min(price, 899.0))
    products.append({"_id": i, "sku": f"SKU-{i:05d}", "name": f"{brand} {base}", "category": cat, "brand": brand, "price": price,
                     "description": f"{brand} {base.lower()} for everyday use. {rnd.choice(GOOD).capitalize()}."})
pop = [rnd.paretovariate(1.2) for _ in products]            # a few products sell a lot — a 'big data' skew
orders = []
for i in range(1, N_ORD + 1):
    items = []
    for p in rnd.choices(products, weights=pop, k=rnd.choices([1, 2, 3, 4, 5], [0.45, 0.25, 0.15, 0.1, 0.05])[0]):
        items.append({"product_id": p["_id"], "qty": rnd.choices([1, 2, 3], [0.8, 0.15, 0.05])[0], "unit_price": p["price"]})
    total = round(sum(x["qty"] * x["unit_price"] for x in items), 2)
    orders.append({"_id": i, "customer_id": rnd.randint(1, N_CUST), "order_date": day(dt.date(2023, 1, 1), dt.date(2025, 12, 31)).isoformat(),
                   "status": pick_status(), "items": items, "total": total})
reviews = []
for i in range(1, N_REV + 1):
    p = rnd.choices(products, weights=pop)[0]; r = rnd.choices([1, 2, 3, 4, 5], [0.08, 0.07, 0.12, 0.3, 0.43])[0]
    bits = rnd.sample(GOOD if r >= 4 else BAD if r <= 2 else GOOD + BAD, 2)
    text = f"{bits[0].capitalize()}, {bits[1]}. Bought the {p['name'].split(' ', 1)[1].lower()} for {rnd.choice(['work', 'travel', 'home', 'a gift', 'camping', 'school'])}."
    if rnd.random() < 0.06:
        for k, v in TYPOS.items(): text = text.replace(k, v)
    reviews.append({"_id": i, "product_id": p["_id"], "customer_id": rnd.randint(1, N_CUST), "rating": r, "title": bits[0].capitalize(),
                    "text": text, "review_date": day(dt.date(2023, 1, 1), dt.date(2025, 12, 31)).isoformat()})
os.makedirs("data", exist_ok=True)
for name, rows in [("customers", customers), ("products", products), ("orders", orders), ("reviews", reviews)]:
    with open(f"data/{name}.jsonl", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    print(f"{name:10s} {len(rows):>8,}  data/{name}.jsonl  {os.path.getsize(f'data/{name}.jsonl')/1e6:6.1f} MB")
if "--load" in sys.argv:
    from pymongo import MongoClient
    db = MongoClient(os.environ["MDB_URI"], appname="adsp32030-a4")["shop_raw"]
    for name, rows in [("customers", customers), ("products", products), ("orders", orders), ("reviews", reviews)]:
        db[name].drop()
        for k in range(0, len(rows), 1000): db[name].insert_many(rows[k:k + 1000], ordered=False)
        print("loaded", name, db[name].estimated_document_count())
