# MongoDB document modeling at scale: an online shop on Atlas

An online-shop dataset (25k customers, 2k products, 250k orders with 512k line items, 120k reviews) redesigned from a
flat, relational-style raw load into a document model built for its access patterns. The work covers indexes proven
with `explain()`, a schema enforced by a validator, Atlas Search, and the same questions asked again in SQL with DuckDB.

Notebook with all outputs: **[a4_shop.ipynb](a4_shop.ipynb)**

## What I built
- **[build_shop.py](build_shop.py)**: builds the new design entirely *inside* the database with aggregation pipelines
  ending in `$out` / `$merge`, so no document crosses the network to the client.
  - `orders` embed a customer snapshot and the product name and category for each line item
  - `products` embed a rating summary and the 20 newest reviews (subset pattern)
  - `reviews` and `customers` stay the source of truth (referenced)
- **[tests/](tests/)**: `build()` run against a hand-checked raw sample in a throwaway local MongoDB. Covers duplicate
  line items, tie-breaking on review dates, and products with no reviews.
- A **rollup collection** for the one access pattern the design serves badly (monthly revenue by category).

## Key results
**ESR index**: `find({status:'shipped', total:{$gt:100}}).sort({order_date:-1})`
| index | plan | keys examined | docs examined | in-memory sort | ms |
|---|---|---|---|---|---|
| none | COLLSCAN → SORT | 0 | 250,000 | yes | 218 |
| **`{status, order_date, total}` (ESR)** | **IXSCAN → FETCH** | 16,665 | **15,570** | **no** | **53** |
| `{status, total, order_date}` (wrong order) | IXSCAN → SORT → FETCH | 15,570 | 15,570 | yes | — |

With `limit 20` the ESR index examines **22 keys and 20 documents**; with no index it still reads all 250,000.

- **Atlas Search vs `$regex`:** both find 19,291 reviews mentioning "battery". `$regex` scans all 120,000 documents
  (COLLSCAN); `$search` reads only the inverted-index posting list. At 100× the reviews, that's 12 M documents scanned vs. the same posting list.
- **Schema as a contract:** `$jsonSchema` validator with required fields, BSON types, a status `enum` and a `schemaVersion`.
  All 250,000 existing documents were confirmed to pass before switching it on.
- **What breaks first at 25 M orders:** the 512 MB free tier, long before the network or the design. `shop.orders`
  would be about 6 GB on disk. A client-side pull would move about 10.8 GB, while pushdown still returns about 8 KB.
- **AI agent with least privilege:** Claude Code reached Atlas only through the MongoDB MCP server, in `--readOnly` mode,
  as a user with the `read` role only (see [screenshots/](screenshots/)).

## Layout
```
a4_shop.ipynb    the assignment: model, query, index, validate, search, SQL vs MQL, the MCP agent
build_shop.py    raw → designed collections, in-database
gen_shop.py      deterministic data generator (seed 32030)
tests/           build() on a hand-checked sample (local MongoDB in Docker)
screenshots/     Atlas Search index, orders validator, read-only database user
```

## Run it
```bash
pip install -r requirements.txt
cp env.example.sh env.sh && $EDITOR env.sh && source env.sh   # your Atlas connection string
python gen_shop.py && python build_shop.py
pytest -q                                                     # skips unless Docker is available
```

## Stack
MongoDB Atlas · aggregation pipelines · `explain()` · Atlas Search · `$jsonSchema` · pymongo · DuckDB · pandas · MCP

---
Course work for *ADSP 32030 Scalable Data Systems*, University of Chicago (Fall 2026).
`gen_shop.py` and `env.example.sh` were provided by the course. The design, `build_shop.py`, tests and notebook are mine.
