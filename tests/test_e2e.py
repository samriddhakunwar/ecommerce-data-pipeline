import json

from fastapi.testclient import TestClient

import app as app_module
import generate_raw_data
from automate_pipeline import DataPipeline


def test_generate_pipeline_api(tmp_path, db_url, engine, monkeypatch):
    raw = tmp_path / "raw.csv"
    generate_raw_data.main(output=raw)
    first = raw.read_bytes()
    generate_raw_data.main(output=raw)
    assert raw.read_bytes() == first  # reproducible

    def run():
        p = DataPipeline(raw_data=raw, db_url=db_url, data_dir=tmp_path, reports_dir=tmp_path)
        assert p.run_pipeline(), p.error
        return p

    p1 = run()
    p2 = run()
    assert p1.table_row_count == p2.table_row_count == p1.cleaning_report["clean_rows"] > 1000
    assert (tmp_path / "rejected_products.csv").exists()
    report = json.loads((tmp_path / "pipeline_execution_report.json").read_text())
    assert report["status"] == "SUCCESS"
    assert report["rows_upserted"] == p2.rows_upserted
    assert report["cleaning"]["categories_mapped_to_other"] > 0

    monkeypatch.setattr(app_module, "engine", engine)
    with TestClient(app_module.app) as client:
        assert client.get("/health").status_code == 200
        products = client.get("/products", params={"limit": 2}).json()
        assert len(products) == 2
        assert client.get("/stats").json()["total_products"] == p1.table_row_count
