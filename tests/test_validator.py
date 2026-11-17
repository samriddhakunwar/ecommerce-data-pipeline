import json

import numpy as np
import pandas as pd
import pytest
from conftest import numbered_rows
from sqlalchemy import inspect

from automate_pipeline import DataPipeline
from clean_data import DataCleaner
from validate_data import DataValidator


@pytest.fixture
def clean_df() -> pd.DataFrame:
    return DataCleaner(df=numbered_rows(5)).run_all_cleaning()


def validate(df: pd.DataFrame, **kw) -> DataValidator:
    v = DataValidator(df=df, **kw)
    v.run_all_validations()
    return v


def test_passes_on_clean_data(clean_df):
    v = validate(clean_df, raw_row_count=len(clean_df))
    assert not v.has_failures, v.failed_checks
    assert v.summary()["failed"] == 0


def _set(col, value):
    def mutate(df):
        df.loc[0, col] = value
        return df
    return mutate


@pytest.mark.parametrize("mutate,check", [
    (_set("product_id", "P001"), "Duplicate Product IDs"),
    (_set("price", -1.0), "Price Validity"),
    (_set("price", np.nan), "Price Validity"),
    (_set("price", 1e9), "Price Upper Bound"),
    (_set("stock", -3), "Stock Validity"),
    (_set("category", "Gadgets"), "Category Validity"),
    (_set("product_name", None), "Product Name Validity"),
    (_set("product_name", "  "), "Product Name Validity"),
    (_set("supplier", None), "Missing Values"),
    (_set("last_updated", "not a date"), "Date Format"),
    (lambda df: df.drop(columns=["stock"]), "Required Columns"),
])
def test_fails_on_bad_data(clean_df, mutate, check):
    df = clean_df.astype(object)
    v = validate(mutate(df))
    assert v.has_failures
    assert any(c.startswith(check) for c in v.failed_checks), v.failed_checks


def test_rejection_rate_threshold(clean_df):
    assert validate(clean_df, raw_row_count=100, max_rejection_pct=40).has_failures
    assert not validate(clean_df, raw_row_count=100, max_rejection_pct=99).has_failures


def test_date_check_does_not_mutate(clean_df):
    df = clean_df.copy()
    df["last_updated"] = df["last_updated"].dt.strftime("%Y-%m-%d")
    validate(df)
    assert df["last_updated"].dtype == object


def _bad_raw(tmp_path):
    raw = tmp_path / "raw.csv"
    # 2 good rows, 8 invalid prices -> 80% rejected, over the 40% default
    pd.concat([numbered_rows(2), numbered_rows(8, price="bad").assign(
        product_id=lambda d: "X" + d["product_id"])]).to_csv(raw, index=False)
    return raw


def test_gate_stops_pipeline_before_upload(tmp_path, db_url, engine):
    p = DataPipeline(raw_data=_bad_raw(tmp_path), db_url=db_url,
                     data_dir=tmp_path, reports_dir=tmp_path)
    assert p.run_pipeline() is False
    assert "products" not in inspect(engine).get_table_names()
    report = json.loads((tmp_path / "pipeline_execution_report.json").read_text())
    assert report["status"] == "FAILED"
    assert report["rows_upserted"] == 0
    assert report["validation"]["failed"] >= 1
    assert "STATUS: FAILED" in (tmp_path / "pipeline_execution_report.txt").read_text()


def test_gate_can_be_overridden(tmp_path, db_url):
    p = DataPipeline(raw_data=_bad_raw(tmp_path), db_url=db_url, allow_validation_failures=True,
                     data_dir=tmp_path, reports_dir=tmp_path)
    assert p.run_pipeline() is True
    assert p.rows_upserted == 2

