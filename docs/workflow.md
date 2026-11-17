# Data Pipeline Workflow

```
data/raw_products.csv
    │  scripts/clean_data.py      DataCleaner
    ├──────────────► data/rejected_products.csv   (every removed row + rejection_reason)
    ▼
data/cleaned_products.csv
    │  scripts/validate_data.py   DataValidator ──► reports/data_quality_report.csv
    │  QUALITY GATE: any FAIL → stop, exit 1 (unless --allow-validation-failures)
    ▼
    │  scripts/upload_to_db.py    DatabaseUploader
    │  create_all() schema + views, upsert by product_id in one transaction, verify
    ▼
products table (SQLite by default; PostgreSQL/MySQL via DATABASE_URL)
    │
    ▼
api/app.py (FastAPI)

scripts/automate_pipeline.py runs all of the above and writes
reports/pipeline_execution_report.txt + .json (status, counts, validation, rows upserted).
```

## 1. Cleaning (`DataCleaner`)

The raw CSV is read as strings so rejected rows keep their original values.
Steps run in this order:

| Step | Rule | rejection_reason |
|------|------|------------------|
| strip_whitespace | strip every string column; `""` → missing | – |
| clean_product_ids | product_id required | `missing_product_id` |
| clean_product_names | name required (blank counts as missing) | `missing_product_name` |
| standardize_categories | `strip().lower()` → map; unknown/missing → `Other` (counted) | – |
| clean_prices | numeric and > 0; rounded to 2 dp | `invalid_price` |
| clean_stock | integer and >= 0 | `invalid_stock` |
| clean_dates | `%Y-%m-%d`, `%d/%m/%Y` or `%m/%d/%Y` | `invalid_date` |
| remove_duplicates | one row per product_id: latest `last_updated` wins | `duplicate_product_id` |
| clean_supplier | missing → `Unknown` | – |

Deduplication runs after the validity filters, so a valid row is never dropped
in favour of a newer invalid one. `cleaning_report` holds the per-step counts.

## 2. Validation (`DataValidator`)

Checks: required columns, missing values per column, duplicate IDs, price > 0,
price <= `--max-price` (default 100,000), stock >= 0, allowed categories,
non-blank names, `YYYY-MM-DD` dates, and rejection rate <= `--max-rejection-pct`
(default 40%). Each check is PASS or FAIL in `reports/data_quality_report.csv`.

## 3. Database upload (`DatabaseUploader`)

- The schema is defined once as a SQLAlchemy Core `Table` + `Index` objects and
  created with `metadata.create_all()`. Views are created per dialect.
- Upsert: SQLite/PostgreSQL `ON CONFLICT (product_id) DO UPDATE`, MySQL
  `ON DUPLICATE KEY UPDATE`. `updated_at` is bumped and `created_at` is kept.
- `verify_upload()` raises if any uploaded product_id is missing from the table.

## 4. API

See the README for endpoints, `API_KEY` and `CORS_ORIGINS`.

## Errors and logging

Logging goes to the console (configured once in each entry point). A failure
in any step marks the run `FAILED` in the execution report and exits with code 1.
