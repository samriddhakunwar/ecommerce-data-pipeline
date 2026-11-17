import io

import pytest
from conftest import make_rows, numbered_rows
from fastapi.testclient import TestClient

import app as app_module
from clean_data import DataCleaner
from upload_to_db import DatabaseUploader, create_schema


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setattr(app_module, "engine", engine)
    monkeypatch.delenv("API_KEY", raising=False)
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def seeded(engine):
    df = numbered_rows(15)
    df.loc[df.index < 4, "category"] = "Storage"
    create_schema(engine)
    DatabaseUploader(engine=engine).upsert_dataframe(DataCleaner(df=df).run_all_cleaning())


def csv_bytes(df) -> bytes:
    return df.to_csv(index=False).encode()


def test_list_and_pagination(client, seeded):
    r = client.get("/products", params={"limit": 5})
    assert r.status_code == 200
    assert [p["product_id"] for p in r.json()] == ["P000", "P001", "P002", "P003", "P004"]
    r = client.get("/products", params={"skip": 10, "limit": 10})
    assert [p["product_id"] for p in r.json()] == [f"P{i:03d}" for i in range(10, 15)]
    assert r.json()[0]["last_updated"] == "2025-01-01"
    assert client.get("/products", params={"limit": 1000}).status_code == 422


def test_get_by_id_and_404(client, seeded):
    r = client.get("/products/P007")
    assert r.status_code == 200
    assert r.json()["product_name"] == "Mouse"
    assert client.get("/products/NOPE").status_code == 404


def test_category_filter_case_insensitive_and_paginated(client, seeded):
    r = client.get("/products/category/sToRaGe")
    assert r.status_code == 200
    assert len(r.json()) == 4
    assert {p["category"] for p in r.json()} == {"Storage"}
    assert len(client.get("/products/category/storage", params={"limit": 3}).json()) == 3
    assert len(client.get("/products/category/storage", params={"skip": 3}).json()) == 1
    assert len(client.get("/products", params={"category": "AUDIO"}).json()) == 10


def test_stats(client, seeded):
    s = client.get("/stats").json()
    assert s["total_products"] == 15
    assert s["categories"] == 2
    assert s["total_stock"] == 45


def test_stats_on_empty_table(client, engine):
    create_schema(engine)
    r = client.get("/stats")
    assert r.status_code == 200
    assert r.json() == {"total_products": 0, "categories": 0, "min_price": None,
                        "max_price": None, "avg_price": None, "total_stock": 0}


def test_health_503_when_table_missing(client):
    r = client.get("/health")
    assert r.status_code == 503
    assert "missing" in r.json()["detail"]
    assert client.get("/products").status_code == 503


def test_health_503_when_empty_then_200(client, engine):
    create_schema(engine)
    assert client.get("/health").status_code == 503
    DatabaseUploader(engine=engine).upsert_dataframe(
        DataCleaner(df=numbered_rows(1)).run_all_cleaning())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_upload_disabled_without_api_key_env(client):
    r = client.post("/upload", files={"file": ("p.csv", csv_bytes(numbered_rows(2)))})
    assert r.status_code == 503


def test_upload_rejected_without_or_with_wrong_key(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    files = {"file": ("p.csv", csv_bytes(numbered_rows(2)))}
    assert client.post("/upload", files=files).status_code == 401
    assert client.post("/upload", files=files, headers={"X-API-Key": "nope"}).status_code == 401


def test_upload_accepted_with_key(client, engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    good = ({"product_id": f"U{i}"} for i in range(9))
    df = make_rows(*good, {"product_id": "BAD", "price": "x"})
    r = client.post("/upload", files={"file": ("p.csv", csv_bytes(df))},
                    headers={"X-API-Key": "s3cret"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_received"] == 10
    assert body["rows_accepted"] == 9
    assert body["rows_rejected"] == 1
    assert body["rejection_reasons"] == {"invalid_price": 1}
    assert client.get("/products/U3").status_code == 200
    # Re-uploading is an upsert, not a duplicate insert
    client.post("/upload", files={"file": ("p.csv", csv_bytes(df))},
                headers={"X-API-Key": "s3cret"})
    assert client.get("/stats").json()["total_products"] == 9


def test_upload_bad_input_does_not_leak_details(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    h = {"X-API-Key": "k"}
    r = client.post("/upload", files={"file": ("p.csv", b"a,b\n1,2\n")}, headers=h)
    assert r.status_code == 400
    assert "Missing required columns" in r.json()["detail"]
    r = client.post("/upload", files={"file": ("p.csv", b"\x00\xff")}, headers=h)
    assert r.status_code == 400
    assert "Traceback" not in r.text


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/upload", files={"file": ("p.csv", io.BytesIO(b"x" * 11))},
                    headers={"X-API-Key": "k"})
    assert r.status_code == 413


def test_old_file_path_upload_is_gone(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    r = client.post("/upload", params={"file_path": "/etc/passwd"}, headers={"X-API-Key": "k"})
    assert r.status_code == 422  # requires a multipart file; file_path is ignored
