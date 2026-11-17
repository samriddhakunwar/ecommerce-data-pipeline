"""
FastAPI application for the e-commerce data pipeline.

Run from the project root:  uvicorn api.app:app --reload
or from api/:               uvicorn app:app --reload
Both use the same database (config.get_db_url(): $DATABASE_URL or the
project-root ecommerce.db).
"""
from __future__ import annotations

import io
import logging
import os
import secrets
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, func, inspect, select

# Make scripts/ importable however the app is launched (from the root or from api/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from clean_data import REQUIRED_COLUMNS, DataCleaner  # noqa: E402
from config import get_db_url  # noqa: E402
from upload_to_db import DatabaseUploader, create_schema, products  # noqa: E402
from validate_data import DataValidator  # noqa: E402

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MiB
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8000,http://127.0.0.1:8000"
)

engine = create_engine(get_db_url())

app = FastAPI(
    title="E-commerce Data Pipeline API",
    description="API for accessing product data from the pipeline",
    version="1.1.0",
)

cors_origins = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,  # wildcard + credentials is invalid
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- models ---------------------------------------------------------------------------
class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    category: str
    price: float
    stock: int
    supplier: str | None = None
    last_updated: date | None = None


class ProductStats(BaseModel):
    total_products: int
    categories: int
    min_price: float | None
    max_price: float | None
    avg_price: float | None
    total_stock: int


class UploadResult(BaseModel):
    status: str
    rows_received: int
    rows_accepted: int
    rows_rejected: int
    rejection_reasons: dict[str, int]


def _table_exists() -> bool:
    return "products" in inspect(engine).get_table_names()


def _require_table() -> None:
    if not _table_exists():
        raise HTTPException(
            status_code=503,
            detail="Database not initialized: run `python scripts/automate_pipeline.py` first",
        )


# --- routes ---------------------------------------------------------------------------
@app.get("/")
def root() -> dict:
    return {
        "message": "E-commerce Data Pipeline API",
        "version": app.version,
        "endpoints": [
            "/products", "/products/{product_id}", "/products/category/{category}",
            "/stats", "/health", "POST /upload",
        ],
    }


@app.get("/products", response_model=list[Product])
def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
) -> list[dict]:
    """List products with pagination and an optional case-insensitive category filter."""
    _require_table()
    query = select(products).order_by(products.c.product_id).offset(skip).limit(limit)
    if category:
        query = query.where(func.lower(products.c.category) == category.strip().lower())
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(query).mappings()]


@app.get("/products/category/{category}", response_model=list[Product])
def get_products_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> list[dict]:
    """Products in a category (case-insensitive), paginated."""
    return get_products(skip=skip, limit=limit, category=category)


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> dict:
    _require_table()
    with engine.connect() as conn:
        row = conn.execute(
            select(products).where(products.c.product_id == product_id)
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict(row)


@app.get("/stats", response_model=ProductStats)
def get_statistics() -> dict:
    """Aggregate statistics. An empty table returns zeros/nulls."""
    _require_table()
    with engine.connect() as conn:
        row = conn.execute(
            select(
                func.count().label("total_products"),
                func.count(products.c.category.distinct()).label("categories"),
                func.min(products.c.price).label("min_price"),
                func.max(products.c.price).label("max_price"),
                func.avg(products.c.price).label("avg_price"),
                func.coalesce(func.sum(products.c.stock), 0).label("total_stock"),
            )
        ).mappings().one()
    stats = dict(row)
    if stats["avg_price"] is not None:
        stats["avg_price"] = round(float(stats["avg_price"]), 2)
    return stats


@app.get("/health", response_model=None)
def health_check() -> dict | JSONResponse:
    """200 only if the products table exists and has rows; otherwise 503."""
    try:
        if not _table_exists():
            return JSONResponse(status_code=503, content={
                "status": "unhealthy", "detail": "products table is missing"})
        with engine.connect() as conn:
            count = conn.execute(select(func.count()).select_from(products)).scalar_one()
    except Exception:  # noqa: BLE001 - any DB error means unhealthy
        logger.exception("Health check failed")
        return JSONResponse(status_code=503, content={
            "status": "unhealthy", "detail": "database unavailable"})
    if count == 0:
        return JSONResponse(status_code=503, content={
            "status": "unhealthy", "detail": "products table is empty"})
    return {"status": "healthy", "database": "connected", "products": count}


@app.post("/upload", response_model=UploadResult)
def upload_file(
    file: Annotated[UploadFile, File()],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict:
    """Upload a CSV; rows go through DataCleaner -> DataValidator -> upsert."""
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Upload disabled: API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    try:
        raw = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception:  # noqa: BLE001 - never echo parser internals
        raise HTTPException(status_code=400, detail="Could not parse file as CSV") from None
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")

    try:
        cleaner = DataCleaner(df=raw)
        cleaned = cleaner.run_all_cleaning()
        validator = DataValidator(df=cleaned)
        validator.run_all_validations()
        if validator.has_failures:
            raise HTTPException(
                status_code=422,
                detail={"message": "Validation failed", "failed_checks": validator.failed_checks},
            )
        uploader = DatabaseUploader(engine=engine)
        create_schema(engine)
        accepted = uploader.upsert_dataframe(cleaned)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - log details server-side only
        logger.exception("Upload processing failed")
        raise HTTPException(status_code=500, detail="Upload failed") from None

    rejected = cleaner.rejected
    return {
        "status": "success",
        "rows_received": len(raw),
        "rows_accepted": accepted,
        "rows_rejected": len(rejected),
        "rejection_reasons": rejected["rejection_reason"].value_counts().to_dict(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
