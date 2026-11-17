# E-commerce Data Pipeline

[![CI](https://github.com/samriddhakunwar/ecommerce-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/samriddhakunwar/ecommerce-data-pipeline/actions/workflows/ci.yml)

A portfolio project: a small batch pipeline that cleans and validates a messy
e-commerce product CSV, upserts it into a SQL database, and serves it through
a FastAPI REST API.

## What it does

1. **Generate** a reproducible, intentionally messy dataset (`generate_raw_data.py`).
2. **Clean** it (`scripts/clean_data.py`):
   - strips whitespace on every string column; blank names count as missing
   - normalizes categories (`strip().lower()` + mapping; unknown ones become `Other`, and the count is logged)
   - rejects invalid prices, stock and dates (several date formats are accepted); rounds prices to 2 decimals
   - deduplicates by `product_id`, keeping the row with the latest `last_updated`
   - writes **every removed row** to `data/rejected_products.csv` with a `rejection_reason`
3. **Validate** the result (`scripts/validate_data.py`): required columns, missing
   values, duplicate IDs, price validity and upper bound, stock, categories,
   names, date format, and the share of raw rows rejected.
   **Quality gate:** if any check fails, the pipeline stops *before* touching
   the database and exits non-zero (override with `--allow-validation-failures`).
4. **Upsert** into the database (`scripts/upload_to_db.py`) in one transaction,
   keyed on `product_id`. Re-running the pipeline is idempotent; `created_at`
   is kept and `updated_at` is bumped on update. The schema (PK, NOT NULL,
   timestamps, indexes, views) is defined once in SQLAlchemy Core.
5. **Report**: `reports/pipeline_execution_report.txt` and `.json` with the real
   status, per-step cleaning counts, validation pass/fail totals and rows upserted.

## Project structure

```
ecommerce-data-pipeline/
├── generate_raw_data.py        # reproducible messy input -> data/raw_products.csv
├── scripts/
│   ├── config.py               # project-root paths, DATABASE_URL, logging setup
│   ├── clean_data.py           # DataCleaner
│   ├── validate_data.py        # DataValidator (quality gate)
│   ├── upload_to_db.py         # canonical schema + upsert (DatabaseUploader)
│   └── automate_pipeline.py    # orchestrator: clean -> validate -> upsert -> report
├── api/app.py                  # FastAPI app
├── streamlit_app.py            # Streamlit dashboard
├── database/schema.sql         # reference copy of the schema (code is canonical)
├── tests/                      # pytest suite (temp dirs + temp SQLite only)
├── data/  reports/             # generated outputs (git-ignored)
└── docs/workflow.md
```

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/samriddhakunwar/ecommerce-data-pipeline.git
cd ecommerce-data-pipeline
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional: pytest, httpx, ruff
```

## Run the pipeline

```bash
python generate_raw_data.py
python scripts/automate_pipeline.py
```

Both commands resolve paths from the project root, so they work from any
working directory. Outputs:

- `data/cleaned_products.csv`, `data/rejected_products.csv`
- `reports/data_quality_report.csv`
- `reports/pipeline_execution_report.txt` and `.json`
- `ecommerce.db` (SQLite, default)

Options for `automate_pipeline.py`:

| Flag | Default | Meaning |
|------|---------|---------|
| `--raw-data PATH` | `data/raw_products.csv` | input CSV |
| `--db-url URL` | `$DATABASE_URL` or `sqlite:///<project>/ecommerce.db` | SQLAlchemy URL |
| `--max-rejection-pct N` | `40` | fail if more than N% of raw rows were rejected |
| `--max-price N` | `100000` | fail if any price is above N |
| `--allow-validation-failures` | off | upload even if checks fail |

The individual steps can also be run on their own: `python scripts/clean_data.py`,
`python scripts/validate_data.py` (exits 1 on failures) and
`python scripts/upload_to_db.py [--db-url URL] [--csv PATH]`.

## Databases

SQLite works out of the box. PostgreSQL and MySQL are supported by the
upsert/view code (`ON CONFLICT` / `ON DUPLICATE KEY UPDATE`, `CREATE OR REPLACE VIEW`).
The CI only runs SQLite, so treat them as lightly tested. Install a driver
and point `DATABASE_URL` (or `--db-url`) at your server:

```bash
# PostgreSQL
pip install "psycopg2-binary>=2.9,<3"
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/ecommerce"

# MySQL
pip install "pymysql>=1.1,<2"
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/ecommerce"

python scripts/automate_pipeline.py
```

(Windows PowerShell: `$env:DATABASE_URL = "..."`.)

## API

Start it from the project root **or** from `api/`. Both use the same database
(`DATABASE_URL`, or the project-root `ecommerce.db`):

```bash
uvicorn api.app:app --reload        # from the project root
cd api && uvicorn app:app --reload  # from api/
```

Docs: `http://localhost:8000/docs`.

| Endpoint | Notes |
|----------|-------|
| `GET /products?skip=0&limit=10&category=audio` | paginated, ordered by `product_id`; category is case-insensitive |
| `GET /products/{product_id}` | 404 if not found |
| `GET /products/category/{category}?skip=&limit=` | case-insensitive, paginated |
| `GET /stats` | counts/min/max/avg; zeros and nulls on an empty table |
| `GET /health` | 200 only if the `products` table exists and has rows, otherwise 503 |
| `POST /upload` | multipart CSV upload (see below) |

```bash
curl "http://localhost:8000/products?limit=2"
curl "http://localhost:8000/products/category/storage?limit=5"
curl "http://localhost:8000/stats"
curl "http://localhost:8000/health"
```

### Upload endpoint

Disabled (503) unless the `API_KEY` environment variable is set. Requests must
send a matching `X-API-Key` header. Files are capped at 5 MiB and go through the
same cleaner, validator and upsert as the pipeline. The response reports
accepted and rejected row counts with reasons. Error responses never include
internal exception text.

```bash
export API_KEY="change-me"
uvicorn api.app:app
curl -X POST -H "X-API-Key: change-me" -F "file=@data/raw_products.csv" http://localhost:8000/upload
```

### CORS

Allowed origins come from `CORS_ORIGINS` (comma-separated). The default is
localhost dev origins (ports 3000, 5173, 8000). If you set it to `*`,
credentials are disabled.

## Dashboard

```bash
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. It reads the same database as the pipeline
(`DATABASE_URL`, or the project-root `ecommerce.db`) and the latest reports,
and shows:

- the last run's status, validation totals and rows upserted
- KPI tiles: products, categories, average price, total stock, low-stock count
- products and average price per category
- rejected rows by reason
- a low-stock table and a filterable product table with CSV download

Category and price filters apply to everything on the page. Data is cached
for 60 seconds; re-run the pipeline and refresh to see new data.

## Tests and linting

```bash
ruff check .
pytest -q
```

The suite covers each cleaning rule, each validation check and the quality
gate, schema preservation and upsert idempotency, the API endpoints (including
the upload auth and the empty/missing-table cases), and an end-to-end run
(generate → pipeline twice → API). Tests use temp directories and a temp SQLite
database only. CI runs both on Python 3.10, 3.11 and 3.12.

## Database schema

Defined in `scripts/upload_to_db.py` (`database/schema.sql` is a reference copy):

```sql
CREATE TABLE products (
    product_id   VARCHAR(50)  NOT NULL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category     VARCHAR(100) NOT NULL,
    price        NUMERIC(10, 2) NOT NULL,
    stock        INTEGER NOT NULL,
    supplier     VARCHAR(255),
    last_updated DATE,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- indexes: idx_category, idx_supplier, idx_price, idx_stock
-- views:   low_stock_products, products_by_category, supplier_statistics
```

## Known limitations / possible next steps

- Batch only: every run re-reads the whole CSV (the upsert makes this safe, not incremental).
- PostgreSQL/MySQL paths are not exercised in CI.
- The upload endpoint uses a single shared API key, with no per-user auth or rate limiting.
- Rows deleted from the source are not deleted from the database.

## License

No license file has been added yet, so all rights are reserved by default.
**TODO (owner):** choose a license (e.g. MIT, Apache-2.0) and add a `LICENSE` file.

## Author

[samriddhakunwar](https://github.com/samriddhakunwar)
