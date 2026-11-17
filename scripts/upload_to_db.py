"""
Database Upload Module

Owns the canonical `products` schema (SQLAlchemy Core) and loads cleaned data
with an idempotent upsert keyed on product_id. Works with SQLite (default),
PostgreSQL and MySQL; the dialect is taken from the database URL.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    bindparam,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection, make_url

from config import CLEANED_DATA, get_db_url, setup_logging

logger = logging.getLogger(__name__)

# --- Canonical schema (database/schema.sql mirrors this for reference) -------------
metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("product_id", String(50), primary_key=True),
    Column("product_name", String(255), nullable=False),
    Column("category", String(100), nullable=False),
    Column("price", Numeric(10, 2, asdecimal=False), nullable=False),
    Column("stock", Integer, nullable=False),
    Column("supplier", String(255)),
    Column("last_updated", Date),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

Index("idx_category", products.c.category)
Index("idx_supplier", products.c.supplier)
Index("idx_price", products.c.price)
Index("idx_stock", products.c.stock)

DATA_COLUMNS = [
    "product_id", "product_name", "category", "price", "stock", "supplier", "last_updated",
]

VIEWS = {
    "low_stock_products": """
        SELECT product_id, product_name, category, stock
        FROM products
        WHERE stock < 10""",
    "products_by_category": """
        SELECT category, COUNT(*) AS product_count, AVG(price) AS avg_price,
               SUM(stock) AS total_stock
        FROM products
        GROUP BY category""",
    "supplier_statistics": """
        SELECT supplier, COUNT(*) AS product_count, AVG(price) AS avg_price,
               MIN(price) AS min_price, MAX(price) AS max_price
        FROM products
        WHERE supplier IS NOT NULL
        GROUP BY supplier""",
}


def create_views(conn: Connection) -> None:
    """Create the reporting views with the syntax the current dialect supports."""
    if conn.dialect.name == "sqlite":
        prefix = "CREATE VIEW IF NOT EXISTS"
    elif conn.dialect.name in ("postgresql", "mysql", "mariadb"):
        prefix = "CREATE OR REPLACE VIEW"
    else:
        raise ValueError(f"Unsupported database dialect: {conn.dialect.name}")
    for name, body in VIEWS.items():
        conn.execute(text(f"{prefix} {name} AS {body}"))


def create_schema(engine: Engine) -> None:
    """Create the products table, its indexes and views if they don't exist."""
    metadata.create_all(engine)
    with engine.begin() as conn:
        create_views(conn)


def _upsert_statement(dialect: str):
    """INSERT ... ON CONFLICT/DUPLICATE KEY UPDATE for products, keyed on product_id."""
    update_cols = [c for c in DATA_COLUMNS if c != "product_id"]
    if dialect in ("sqlite", "postgresql"):
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        stmt = insert(products)
        set_ = {c: stmt.excluded[c] for c in update_cols}
        set_["updated_at"] = func.current_timestamp()
        return stmt.on_conflict_do_update(index_elements=["product_id"], set_=set_)
    if dialect in ("mysql", "mariadb"):
        from sqlalchemy.dialects.mysql import insert

        stmt = insert(products)
        set_ = {c: stmt.inserted[c] for c in update_cols}
        set_["updated_at"] = func.current_timestamp()
        return stmt.on_duplicate_key_update(set_)
    raise ValueError(f"Upsert not supported for dialect: {dialect}")


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a cleaned DataFrame into DB-ready dicts (real dates, native types)."""
    out = df[DATA_COLUMNS].copy()
    out["last_updated"] = pd.to_datetime(out["last_updated"]).dt.date
    out["price"] = out["price"].astype(float).round(2)
    out["stock"] = out["stock"].astype(int)
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict(orient="records")


class DatabaseUploader:
    """Handle database operations for product data."""

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = get_db_url(db_url)
        self.engine: Engine | None = None

    @property
    def dialect(self) -> str:
        return make_url(self.db_url).get_backend_name()

    def connect(self) -> Engine:
        """Create the SQLAlchemy engine."""
        self.engine = create_engine(self.db_url)
        safe_url = make_url(self.db_url).render_as_string(hide_password=True)
        logger.info("Connected to %s database (%s)", self.dialect, safe_url)
        return self.engine

    def create_schema(self) -> None:
        """Create tables, indexes and views if they don't exist."""
        create_schema(self.engine)
        logger.info("Schema ready (products table, indexes, views)")

    def upsert_dataframe(self, df: pd.DataFrame) -> int:
        """Upsert all rows in one transaction. Returns the number of rows written."""
        if df["product_id"].duplicated().any():
            raise ValueError("Cannot upsert: duplicate product_id values in input")
        records = dataframe_to_records(df)
        if not records:
            logger.info("Nothing to upsert")
            return 0
        stmt = _upsert_statement(self.dialect)
        with self.engine.begin() as conn:
            conn.execute(stmt, records)
        logger.info("Upserted %d rows into products", len(records))
        return len(records)

    def upload_data(self, csv_file: str | Path) -> int:
        """Load a cleaned CSV and upsert it. Returns the number of rows written."""
        df = pd.read_csv(csv_file, dtype={"product_id": str})
        logger.info("Loading %d rows from %s", len(df), csv_file)
        return self.upsert_dataframe(df)

    def verify_upload(self, df_or_ids: pd.DataFrame | list[str]) -> int:
        """Check that every uploaded product_id is present in the DB.

        Raises RuntimeError on mismatch. Returns the total table row count.
        """
        ids = list(df_or_ids["product_id"]) if isinstance(df_or_ids, pd.DataFrame) else df_or_ids
        if "products" not in inspect(self.engine).get_table_names():
            raise RuntimeError("Verification failed: table 'products' does not exist")
        with self.engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(products)).scalar_one()
            found = 0
            # Chunk the IN list to stay under driver parameter limits.
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                found += conn.execute(
                    select(func.count()).select_from(products).where(
                        products.c.product_id.in_(bindparam("ids", expanding=True))
                    ),
                    {"ids": chunk},
                ).scalar_one()
        if found != len(ids):
            raise RuntimeError(
                f"Verification failed: uploaded {len(ids)} rows but only {found} found in DB"
            )
        logger.info("Verified %d uploaded rows (table now has %d rows)", found, total)
        return total

    def get_statistics(self) -> dict:
        """Return (and print) basic statistics about the products table."""
        with self.engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count().label("total_products"),
                    func.count(products.c.category.distinct()).label("categories"),
                    func.min(products.c.price).label("min_price"),
                    func.max(products.c.price).label("max_price"),
                    func.avg(products.c.price).label("avg_price"),
                    func.sum(products.c.stock).label("total_stock"),
                    func.count(products.c.supplier.distinct()).label("suppliers"),
                )
            ).mappings().one()
        stats = dict(row)
        print("\n" + "=" * 50)
        print("DATABASE STATISTICS")
        print("=" * 50)
        for key, value in stats.items():
            print(f"{key}: {value}")
        return stats

    def close(self) -> None:
        """Dispose of the engine's connection pool."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upsert cleaned products into the database")
    parser.add_argument("--db-url", help="SQLAlchemy URL (default: $DATABASE_URL or local SQLite)")
    parser.add_argument("--csv", default=str(CLEANED_DATA), help="Cleaned CSV to upload")
    args = parser.parse_args()

    setup_logging()
    uploader = DatabaseUploader(db_url=args.db_url)
    uploader.connect()
    try:
        uploader.create_schema()
        df = pd.read_csv(args.csv, dtype={"product_id": str})
        uploader.upsert_dataframe(df)
        uploader.verify_upload(df)
        uploader.get_statistics()
    finally:
        uploader.close()


if __name__ == "__main__":
    main()
