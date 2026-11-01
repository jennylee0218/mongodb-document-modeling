"""build_shop.build() on a hand-checked raw sample, in a throwaway local MongoDB.

Raw sample:
  customers 1 Ava Kim (Chicago, IL, gold), 2 Liam Chen (Austin, TX, bronze)
  products  1 Acme Webcam (Electronics), 2 Midway Yoga Mat (Sports & Outdoors), 3 Loop Labs Kettle (no reviews)
  orders    1: cust 1, [p1 x2 @10.00, p2 x1 @5.50] = 25.50, 2025-01-15
            2: cust 2, [p2 x3 @5.50] = 16.50, 2024-12-31
            3: cust 1, [p1 x1 @10.00, p1 x1 @10.00] = 20.00, 2025-02-01   (same product twice — the generator does this)
  reviews   p1: 25 reviews, review i on 2025-01-i, rating (i % 5) + 1 -> each of 1..5 five times -> avg 3.0, count 25;
                20 newest = days 25 down to 6.
            p2: 2 reviews on the same day, ids 101 (rating 4) and 102 (rating 2) -> avg 3.0; tie broken by _id desc -> 102 first.
"""
import datetime as dt
import pytest
from build_shop import build


def raw_docs():
    customers = [{"_id": 1, "name": "Ava Kim", "email": "user1@example.com", "city": "Chicago", "state": "IL", "tier": "gold",
                  "signup_date": "2022-03-04"},
                 {"_id": 2, "name": "Liam Chen", "email": "user2@example.com", "city": "Austin", "state": "TX", "tier": "bronze",
                  "signup_date": "2023-07-08"}]
    products = [{"_id": 1, "sku": "SKU-00001", "name": "Acme Webcam", "category": "Electronics", "brand": "Acme", "price": 10.0},
                {"_id": 2, "sku": "SKU-00002", "name": "Midway Yoga Mat", "category": "Sports & Outdoors", "brand": "Midway", "price": 5.5},
                {"_id": 3, "sku": "SKU-00003", "name": "Loop Labs Kettle", "category": "Home & Kitchen", "brand": "Loop Labs", "price": 30.0}]
    orders = [{"_id": 1, "customer_id": 1, "order_date": "2025-01-15", "status": "delivered",
               "items": [{"product_id": 1, "qty": 2, "unit_price": 10.0}, {"product_id": 2, "qty": 1, "unit_price": 5.5}], "total": 25.5},
              {"_id": 2, "customer_id": 2, "order_date": "2024-12-31", "status": "shipped",
               "items": [{"product_id": 2, "qty": 3, "unit_price": 5.5}], "total": 16.5},
              {"_id": 3, "customer_id": 1, "order_date": "2025-02-01", "status": "returned",
               "items": [{"product_id": 1, "qty": 1, "unit_price": 10.0}, {"product_id": 1, "qty": 1, "unit_price": 10.0}], "total": 20.0}]
    reviews = [{"_id": i, "product_id": 1, "customer_id": 1, "rating": i % 5 + 1, "title": f"t{i}", "text": f"text {i}",
                "review_date": f"2025-01-{i:02d}"} for i in range(1, 26)]
    reviews += [{"_id": 101, "product_id": 2, "customer_id": 2, "rating": 4, "title": "a", "text": "a", "review_date": "2025-03-01"},
                {"_id": 102, "product_id": 2, "customer_id": 1, "rating": 2, "title": "b", "text": "b", "review_date": "2025-03-01"}]
    return {"customers": customers, "products": products, "orders": orders, "reviews": reviews}


@pytest.fixture(scope="module")
def shop(local_mongo):
    raw = local_mongo["t_shop_raw"]
    for name, docs in raw_docs().items():
        raw[name].drop(); raw[name].insert_many(docs)
    counts = build(local_mongo, src="t_shop_raw", dst="t_shop")
    return local_mongo["t_shop"], counts


def test_counts(shop):
    assert shop[1] == {"customers": 2, "products": 3, "reviews": 27, "orders": 3}


def test_order_embeds_customer_summary_and_product_names(shop):
    o = shop[0].orders.find_one({"_id": 1})
    assert o["customer"] == {"name": "Ava Kim", "city": "Chicago", "state": "IL", "tier": "gold"}
    assert o["items"] == [{"product_id": 1, "name": "Acme Webcam", "category": "Electronics", "qty": 2, "unit_price": 10.0},
                          {"product_id": 2, "name": "Midway Yoga Mat", "category": "Sports & Outdoors", "qty": 1, "unit_price": 5.5}]
    assert o["order_date"] == dt.datetime(2025, 1, 15) and o["total"] == 25.5 and o["status"] == "delivered"
    assert set(o) == {"_id", "customer_id", "customer", "order_date", "status", "items", "total"}


def test_repeated_product_in_one_order_keeps_both_lines(shop):
    o = shop[0].orders.find_one({"_id": 3})
    assert [(i["product_id"], i["name"], i["qty"]) for i in o["items"]] == [(1, "Acme Webcam", 1), (1, "Acme Webcam", 1)]


def test_product_rating_and_newest_20(shop):
    p = shop[0].products.find_one({"_id": 1})
    assert p["rating"] == {"avg": 3.0, "count": 25}
    days = [r["review_date"].day for r in p["recent_reviews"]]
    assert days == list(range(25, 5, -1))          # 20 newest, newest first
    assert set(p["recent_reviews"][0]) == {"_id", "customer_id", "rating", "title", "text", "review_date"}


def test_review_tie_broken_by_id_and_product_without_reviews(shop):
    p2 = shop[0].products.find_one({"_id": 2})
    assert p2["rating"] == {"avg": 3.0, "count": 2} and [r["_id"] for r in p2["recent_reviews"]] == [102, 101]
    p3 = shop[0].products.find_one({"_id": 3})
    assert p3["rating"] == {"avg": None, "count": 0} and p3["recent_reviews"] == []


def test_dates_are_dates_and_indexes_exist(shop):
    db = shop[0]
    assert isinstance(db.customers.find_one({"_id": 2})["signup_date"], dt.datetime)
    assert isinstance(db.reviews.find_one({"_id": 1})["review_date"], dt.datetime)
    assert "customer_recent" in db.orders.index_information() and "product_recent" in db.reviews.index_information()


def test_revenue_by_month_and_category(shop):
    # Jan 2025: order 1 only -> Electronics 2*10.00 = 20.00, Sports & Outdoors 1*5.50 = 5.50. Feb 2025: Electronics 20.00.
    rows = list(shop[0].orders.aggregate([
        {"$match": {"order_date": {"$gte": dt.datetime(2025, 1, 1), "$lt": dt.datetime(2026, 1, 1)}}},
        {"$unwind": "$items"},
        {"$group": {"_id": {"m": {"$dateToString": {"date": "$order_date", "format": "%Y-%m"}}, "c": "$items.category"},
                    "rev": {"$sum": {"$multiply": ["$items.qty", "$items.unit_price"]}}}},
        {"$sort": {"_id.m": 1, "_id.c": 1}}]))
    assert [(r["_id"]["m"], r["_id"]["c"], r["rev"]) for r in rows] == [
        ("2025-01", "Electronics", 20.0), ("2025-01", "Sports & Outdoors", 5.5), ("2025-02", "Electronics", 20.0)]
