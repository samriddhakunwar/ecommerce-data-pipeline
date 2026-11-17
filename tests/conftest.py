import os

# Safety net: anything that falls back to the default DB URL gets an in-memory DB,
# never the real ecommerce.db. Must be set before the app module is imported.
os.environ["DATABASE_URL"] = "sqlite://"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

GOOD_ROW = {
    "product_id": "P1",
    "product_name": "Mouse",
    "category": "Audio",
    "price": "10.50",
    "stock": "3",
    "supplier": "Acme",
    "last_updated": "2025-01-01",
}


def make_rows(*overrides: dict) -> pd.DataFrame:
    """Build a raw (all-string) DataFrame; each dict overrides GOOD_ROW fields."""
    return pd.DataFrame([{**GOOD_ROW, **o} for o in overrides])


def numbered_rows(n: int, **fields) -> pd.DataFrame:
    return make_rows(*({"product_id": f"P{i:03d}", **fields} for i in range(n)))


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def engine(db_url):
    eng = create_engine(db_url)
    yield eng
    eng.dispose()
