"""Build the A4 design (database `shop`) from the raw load (`shop_raw`), entirely inside the database.
   python build_shop.py            (reads MDB_URI; source env.sh first)
Every step is an aggregation ending in $out / $merge, so no document crosses the network to this machine.

Design — embedded where the access patterns read together, referenced where data is unbounded or shared:
  orders     {_id, customer_id, customer:{name, city, state, tier}, order_date: Date, status,
              items:[{product_id, name, category, qty, unit_price}], total}
  products   {_id, sku, name, category, brand, price, description,
              rating:{avg, count}, recent_reviews:[20 newest {_id, customer_id, rating, title, text, review_date}]}
  reviews    {_id, product_id, customer_id, rating, title, text, review_date: Date}     — source of truth, all 120k
  customers  {_id, name, email, city, state, tier, signup_date: Date}                    — source of truth
"""
import os, sys
from pymongo import MongoClient

RECENT_N = 20


def build(client, src="shop_raw", dst="shop", recent_n=RECENT_N):
    s, d = client[src], client[dst]
    for c in ("customers", "products", "reviews", "orders"):
        d[c].drop()

    # customers: dates become real Dates
    s.customers.aggregate([{"$set": {"signup_date": {"$toDate": "$signup_date"}}},
                           {"$out": {"db": dst, "coll": "customers"}}])

    # reviews: same, kept whole as the source of truth (and the Atlas Search target)
    s.reviews.aggregate([{"$set": {"review_date": {"$toDate": "$review_date"}}},
                         {"$out": {"db": dst, "coll": "reviews"}}])

    # products: start with an empty rating summary, then merge in the computed one (computed + subset patterns)
    s.products.aggregate([{"$set": {"rating": {"avg": None, "count": 0}, "recent_reviews": []}},
                          {"$out": {"db": dst, "coll": "products"}}])
    d.reviews.aggregate([
        {"$group": {"_id": "$product_id",
                    "avg": {"$avg": "$rating"}, "count": {"$sum": 1},
                    "recent_reviews": {"$topN": {"n": recent_n, "sortBy": {"review_date": -1, "_id": -1},
                                                 "output": {"_id": "$_id", "customer_id": "$customer_id", "rating": "$rating",
                                                            "title": "$title", "text": "$text", "review_date": "$review_date"}}}}},
        {"$project": {"rating": {"avg": "$avg", "count": "$count"}, "recent_reviews": 1}},
        {"$merge": {"into": {"db": dst, "coll": "products"}, "on": "_id", "whenMatched": "merge", "whenNotMatched": "discard"}}])

    # orders: embed a customer summary and, per line item, the product name and category (extended reference)
    s.orders.aggregate([
        {"$lookup": {"from": "customers", "localField": "customer_id",
                     "foreignField": "_id", "as": "cust"}},
        {"$lookup": {"from": "products", "localField": "items.product_id", "foreignField": "_id", "as": "prods",
                     "pipeline": [{"$project": {"name": 1, "category": 1}}]}},
        {"$replaceWith": {
            "_id": "$_id", "customer_id": "$customer_id",
            "customer": {"$let": {"vars": {"c": {"$first": "$cust"}},
                                  "in": {"name": "$$c.name", "city": "$$c.city", "state": "$$c.state", "tier": "$$c.tier"}}},
            "order_date": {"$toDate": "$order_date"}, "status": "$status",
            "items": {"$map": {"input": "$items", "as": "it", "in": {"$let": {
                "vars": {"p": {"$first": {"$filter": {"input": "$prods", "cond": {"$eq": ["$$this._id", "$$it.product_id"]}}}}},
                "in": {"product_id": "$$it.product_id", "name": "$$p.name", "category": "$$p.category",
                       "qty": "$$it.qty", "unit_price": "$$it.unit_price"}}}}},
            "total": "$total"}},
        {"$out": {"db": dst, "coll": "orders"}}], allowDiskUse=True)

    # indexes for the access patterns (Part 3's ESR index is built, and proven, in the notebook)
    d.orders.create_index([("customer_id", 1), ("order_date", -1)], name="customer_recent")   # pattern 1
    d.reviews.create_index([("product_id", 1), ("review_date", -1)], name="product_recent")   # full review history per product
    return {c: d[c].count_documents({}) for c in ("customers", "products", "reviews", "orders")}


if __name__ == "__main__":
    client = MongoClient(os.environ["MDB_URI"], appname="adsp32030-a4")
    for k, v in build(client).items():
        print(f"shop.{k:10s} {v:>8,}")
    sys.exit(0)
