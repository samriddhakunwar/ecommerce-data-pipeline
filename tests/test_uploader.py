import pytest
from conftest import numbered_rows
from sqlalchemy import inspect, text

from clean_data import DataCleaner
from upload_to_db import DatabaseUploader


def cleaned(n=5, **fields):
    return DataCleaner(df=numbered_rows(n, **fields)).run_all_cleaning()


@pytest.fixture
def uploader(db_url):
    u = DatabaseUploader(db_url=db_url)
    u.connect()
    u.create_schema()
    yield u
    u.close()


def count(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM products")).scalar_one()


def test_schema_survives_upload(uploader):
    uploader.upsert_dataframe(cleaned())
    insp = inspect(uploader.engine)
    assert insp.get_pk_constraint("products")["constrained_columns"] == ["product_id"]
    cols = {c["name"]: c for c in insp.get_columns("products")}
    for name in ["product_name", "category", "price", "stock", "created_at", "updated_at"]:
        assert cols[name]["nullable"] is False, name
    assert {"idx_category", "idx_supplier", "idx_price", "idx_stock"} <= {
        i["name"] for i in insp.get_indexes("products")}
    assert {"low_stock_products", "products_by_category", "supplier_statistics"} <= set(
        insp.get_view_names())


def test_last_updated_stored_as_date(uploader):
    uploader.upsert_dataframe(cleaned(1))
    with uploader.engine.connect() as conn:
        assert conn.execute(text("SELECT last_updated FROM products")).scalar_one() == "2025-01-01"


def test_running_twice_is_idempotent(uploader):
    df = cleaned(5)
    uploader.upsert_dataframe(df)
    uploader.create_schema()  # schema creation is also repeatable
    uploader.upsert_dataframe(df)
    assert count(uploader.engine) == 5
    with uploader.engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(DISTINCT product_id) FROM products")).scalar_one() == 5


def test_upsert_updates_changed_rows_and_keeps_created_at(uploader):
    uploader.upsert_dataframe(cleaned(3))
    old = "2000-01-01 00:00:00"
    with uploader.engine.begin() as conn:
        conn.execute(text("UPDATE products SET created_at = :t, updated_at = :t"), {"t": old})

    df = cleaned(3)
    df.loc[df["product_id"] == "P001", "price"] = 99.99
    uploader.upsert_dataframe(df)

    with uploader.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT price, created_at, updated_at FROM products WHERE product_id = 'P001'"
        )).one()
    assert row.price == 99.99
    assert row.created_at == old
    assert row.updated_at != old
    assert count(uploader.engine) == 3


def test_verify_upload_fails_loudly_on_mismatch(uploader):
    df = cleaned(2)
    uploader.upsert_dataframe(df)
    assert uploader.verify_upload(df) == 2
    with pytest.raises(RuntimeError, match="uploaded 3 rows but only 2"):
        uploader.verify_upload([*df["product_id"], "MISSING"])


def test_upsert_rejects_duplicate_ids(uploader):
    df = cleaned(2)
    df.loc[1, "product_id"] = df.loc[0, "product_id"]
    with pytest.raises(ValueError, match="duplicate"):
        uploader.upsert_dataframe(df)
