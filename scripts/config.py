"""
Shared configuration: project paths, database URL and logging setup.

Every path is resolved from the project root, so the pipeline and the API
behave the same no matter which directory they are started from.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

RAW_DATA = DATA_DIR / "raw_products.csv"
CLEANED_DATA = DATA_DIR / "cleaned_products.csv"
REJECTED_DATA = DATA_DIR / "rejected_products.csv"
QUALITY_REPORT = REPORTS_DIR / "data_quality_report.csv"
EXECUTION_REPORT = REPORTS_DIR / "pipeline_execution_report.txt"

DEFAULT_DB_URL = f"sqlite:///{(PROJECT_ROOT / 'ecommerce.db').as_posix()}"


def get_db_url(override: str | None = None) -> str:
    """Return the database URL: explicit override > $DATABASE_URL > local SQLite file."""
    return override or os.environ.get("DATABASE_URL") or DEFAULT_DB_URL


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging. Call this from entry points only."""
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
