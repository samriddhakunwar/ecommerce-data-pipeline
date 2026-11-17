import pandas as pd
import pytest
from conftest import make_rows

from clean_data import DataCleaner


def clean(df: pd.DataFrame) -> DataCleaner:
    c = DataCleaner(df=df)
    c.run_all_cleaning()
    return c


def test_dedupe_by_id_keeps_latest_date():
    c = clean(make_rows(
        {"product_id": "P1", "price": "20", "last_updated": "2025-02-01"},
        {"product_id": "P1", "price": "10", "last_updated": "2025-01-01"},
        {"product_id": "P2"},
        {"product_id": "P2"},  # exact duplicate
    ))
    assert sorted(c.df["product_id"]) == ["P1", "P2"]
    assert c.df.set_index("product_id").loc["P1", "price"] == 20.0
    assert c.get_report()["duplicates_removed"] == 2
    assert (c.rejected["rejection_reason"] == "duplicate_product_id").sum() == 2


def test_dedupe_prefers_valid_row_over_newer_invalid_one():
    c = clean(make_rows(
        {"price": "bad", "last_updated": "2025-06-01"},
        {"price": "5", "last_updated": "2025-01-01"},
    ))
    assert c.df["price"].tolist() == [5.0]


def test_missing_and_blank_names_rejected_and_whitespace_stripped():
    c = clean(make_rows(
        {"product_id": "A", "product_name": None},
        {"product_id": "B", "product_name": "   "},
        {"product_id": "C", "product_name": "  Mouse  ", "supplier": "  Acme "},
    ))
    assert c.df["product_id"].tolist() == ["C"]
    assert c.df.loc[0, "product_name"] == "Mouse"
    assert c.df.loc[0, "supplier"] == "Acme"
    assert c.get_report()["missing_names_removed"] == 2


def test_category_normalization_and_other_count():
    c = clean(make_rows(
        {"product_id": "A", "category": " ELECTRONICS "},
        {"product_id": "B", "category": "storage"},
        {"product_id": "C", "category": "Gadgets"},
        {"product_id": "D", "category": None},
    ))
    assert c.df["category"].tolist() == ["Electronics", "Storage", "Other", "Other"]
    assert c.get_report()["categories_mapped_to_other"] == 2


@pytest.mark.parametrize("field,value,reason", [
    ("price", "N/A", "invalid_price"),
    ("price", "", "invalid_price"),
    ("price", "-5", "invalid_price"),
    ("price", "0", "invalid_price"),
    ("stock", None, "invalid_stock"),
    ("stock", "-1", "invalid_stock"),
    ("stock", "2.5", "invalid_stock"),
    ("last_updated", "2025-13-45", "invalid_date"),
    ("last_updated", "yesterday", "invalid_date"),
    ("product_id", None, "missing_product_id"),
])
def test_invalid_values_rejected_with_reason(field, value, reason):
    c = clean(make_rows({field: value}))
    assert c.df.empty
    assert c.rejected["rejection_reason"].tolist() == [reason]


def test_alternate_date_formats_and_price_rounding():
    c = clean(make_rows(
        {"product_id": "A", "last_updated": "31/12/2024", "price": "10.126"},
        {"product_id": "B", "last_updated": "12/31/2024"},
    ))
    assert c.df["last_updated"].dt.strftime("%Y-%m-%d").tolist() == ["2024-12-31"] * 2
    assert c.df.loc[0, "price"] == 10.13


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="Missing required columns"):
        clean(make_rows({}).drop(columns=["price"]))


def test_rejected_file_written_with_reasons(tmp_path):
    raw = tmp_path / "raw.csv"
    make_rows(
        {"product_id": "A"},
        {"product_id": "B", "price": "x"},
        {"product_id": "C", "product_name": ""},
    ).to_csv(raw, index=False)
    c = DataCleaner(raw)
    c.run_all_cleaning()
    out = tmp_path / "sub" / "rejected.csv"
    c.save_rejected_data(out)
    rejected = pd.read_csv(out)
    assert set(rejected["rejection_reason"]) == {"invalid_price", "missing_product_name"}
    assert rejected.loc[rejected["product_id"] == "B", "price"].item() == "x"  # original value
    assert c.get_report()["rejected_rows"] == 2
    assert c.get_report()["clean_rows"] == 1
