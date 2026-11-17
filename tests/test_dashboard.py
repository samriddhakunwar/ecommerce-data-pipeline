from pathlib import Path

import pytest
from conftest import numbered_rows

from clean_data import DataCleaner
from upload_to_db import DatabaseUploader, create_schema

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def run(monkeypatch, db_url):
    monkeypatch.setenv("DATABASE_URL", db_url)
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def test_dashboard_without_data_shows_hint(monkeypatch, db_url):
    monkeypatch.setenv("DASHBOARD_AUTOBUILD", "0")
    at = run(monkeypatch, db_url)
    assert "No product data yet" in at.warning[0].value


def test_dashboard_cold_start_builds_data(monkeypatch, db_url, tmp_path):
    """Simulates Streamlit Community Cloud: no DB, no data files -> the app builds them."""
    import config

    data_dir, reports_dir = tmp_path / "data", tmp_path / "reports"
    data_dir.mkdir()
    reports_dir.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(config, "RAW_DATA", data_dir / "raw_products.csv")
    monkeypatch.setattr(config, "REJECTED_DATA", data_dir / "rejected_products.csv")
    monkeypatch.setattr(config, "EXECUTION_REPORT", reports_dir / "pipeline_execution_report.txt")
    monkeypatch.setenv("DASHBOARD_AUTOBUILD", "1")

    at = run(monkeypatch, db_url)
    assert not at.warning
    assert int({m.label: m.value for m in at.metric}["Products"].replace(",", "")) > 1000
    assert (data_dir / "raw_products.csv").exists()


def test_dashboard_with_data(monkeypatch, db_url, engine):
    df = numbered_rows(12, stock="50")
    df.loc[df.index < 3, "category"] = "Storage"
    df.loc[0, "stock"] = "2"
    create_schema(engine)
    DatabaseUploader(engine=engine).upsert_dataframe(DataCleaner(df=df).run_all_cleaning())

    at = run(monkeypatch, db_url)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Products"] == "12"
    assert metrics["Categories"] == "2"
    assert metrics["Low stock (<10)"] == "1"

    at.multiselect[0].set_value(["Storage"]).run()
    assert {m.label: m.value for m in at.metric}["Products"] == "3"
