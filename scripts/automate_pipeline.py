"""
Automation Pipeline Orchestrator

clean -> validate (quality gate) -> upsert to DB -> report
Run from anywhere: python scripts/automate_pipeline.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import make_url

from clean_data import DataCleaner
from config import DATA_DIR, RAW_DATA, REPORTS_DIR, get_db_url, setup_logging
from upload_to_db import DatabaseUploader
from validate_data import DEFAULT_MAX_PRICE, DEFAULT_MAX_REJECTION_PCT, DataValidator

logger = logging.getLogger(__name__)


class ValidationGateError(RuntimeError):
    """Raised when validation fails and failures are not allowed."""


class DataPipeline:
    """Orchestrate the entire data pipeline."""

    def __init__(
        self,
        raw_data: str | Path = RAW_DATA,
        db_url: str | None = None,
        allow_validation_failures: bool = False,
        max_rejection_pct: float = DEFAULT_MAX_REJECTION_PCT,
        max_price: float = DEFAULT_MAX_PRICE,
        data_dir: Path = DATA_DIR,
        reports_dir: Path = REPORTS_DIR,
    ) -> None:
        self.raw_data = Path(raw_data)
        self.db_url = get_db_url(db_url)
        self.allow_validation_failures = allow_validation_failures
        self.max_rejection_pct = max_rejection_pct
        self.max_price = max_price
        self.cleaned_data = Path(data_dir) / "cleaned_products.csv"
        self.rejected_data = Path(data_dir) / "rejected_products.csv"
        self.validation_report = Path(reports_dir) / "data_quality_report.csv"
        self.execution_report = Path(reports_dir) / "pipeline_execution_report.txt"
        self.status = "NOT RUN"
        self.error: str | None = None
        self.cleaning_report: dict[str, int] = {}
        self.validation_summary: dict[str, int] = {}
        self.failed_checks: list[str] = []
        self.rows_upserted = 0
        self.table_row_count: int | None = None
        self.start_time = 0.0
        self.end_time = 0.0

    def run_pipeline(self) -> bool:
        """Execute the full pipeline. Returns True on success."""
        self.start_time = time.time()
        print("\n" + "=" * 70 + "\nE-COMMERCE DATA PIPELINE AUTOMATION\n" + "=" * 70)
        try:
            print("\n[STEP 1/4] CLEANING DATA...")
            cleaned = self._step_cleaning()
            print("\n[STEP 2/4] VALIDATING DATA...")
            self._step_validation(cleaned)
            print("\n[STEP 3/4] UPLOADING TO DATABASE...")
            self._step_database_upload()
            self.status = "SUCCESS"
        except Exception as e:  # noqa: BLE001 - top-level: record and report any failure
            self.status = "FAILED"
            self.error = str(e)
            logger.error("Pipeline execution failed: %s", e)
        finally:
            self.end_time = time.time()
            print("\n[STEP 4/4] GENERATING REPORT...")
            self._step_generate_report()
        self._print_summary()
        return self.status == "SUCCESS"

    def _step_cleaning(self) -> pd.DataFrame:
        cleaner = DataCleaner(self.raw_data)
        df = cleaner.run_all_cleaning()
        cleaner.save_cleaned_data(self.cleaned_data)
        cleaner.save_rejected_data(self.rejected_data)
        self.cleaning_report = cleaner.get_report()
        return df

    def _step_validation(self, cleaned: pd.DataFrame) -> None:
        validator = DataValidator(
            df=cleaned,
            raw_row_count=self.cleaning_report.get("raw_rows"),
            max_price=self.max_price,
            max_rejection_pct=self.max_rejection_pct,
        )
        validator.run_all_validations()
        validator.save_report(self.validation_report)
        self.validation_summary = validator.summary()
        self.failed_checks = validator.failed_checks
        if validator.has_failures:
            msg = f"Validation failed: {', '.join(self.failed_checks)}"
            if not self.allow_validation_failures:
                raise ValidationGateError(msg + " (use --allow-validation-failures to override)")
            logger.warning("%s; continuing because --allow-validation-failures is set", msg)

    def _step_database_upload(self) -> None:
        uploader = DatabaseUploader(db_url=self.db_url)
        uploader.connect()
        try:
            uploader.create_schema()
            # Upload exactly what was written to disk, so the CSV and the DB agree.
            df = pd.read_csv(self.cleaned_data, dtype={"product_id": str})
            self.rows_upserted = uploader.upsert_dataframe(df)
            self.table_row_count = uploader.verify_upload(df)
            uploader.get_statistics()
        finally:
            uploader.close()

    def report_data(self) -> dict:
        return {
            "status": self.status,
            "error": self.error,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time)),
            "duration_seconds": round(self.end_time - self.start_time, 2),
            "files": {
                "raw_data": str(self.raw_data),
                "cleaned_data": str(self.cleaned_data),
                "rejected_data": str(self.rejected_data),
                "validation_report": str(self.validation_report),
            },
            "database": make_url(self.db_url).render_as_string(hide_password=True),
            "cleaning": self.cleaning_report,
            "validation": {**self.validation_summary, "failed_checks": self.failed_checks},
            "rows_upserted": self.rows_upserted,
            "table_row_count": self.table_row_count,
        }

    def _step_generate_report(self) -> None:
        data = self.report_data()
        lines = [
            "DATA PIPELINE EXECUTION REPORT",
            "=" * 70,
            f"STATUS: {data['status']}",
        ]
        if data["error"]:
            lines.append(f"ERROR: {data['error']}")
        lines += [
            f"Execution Time: {data['started_at']}",
            f"Pipeline Duration: {data['duration_seconds']:.2f} seconds",
            "",
            "FILES:",
            *[f"- {k}: {v}" for k, v in data["files"].items()],
            "",
            "CLEANING (per-step counts):",
            *[f"- {k}: {v}" for k, v in data["cleaning"].items()],
            "",
            "VALIDATION:",
            f"- total checks: {self.validation_summary.get('total', 0)}",
            f"- passed: {self.validation_summary.get('passed', 0)}",
            f"- failed: {self.validation_summary.get('failed', 0)}",
            *[f"  FAIL: {c}" for c in self.failed_checks],
            "",
            "DATABASE:",
            f"- url: {data['database']}",
            f"- rows upserted: {data['rows_upserted']}",
            f"- table row count: {data['table_row_count']}",
            "",
        ]
        self.execution_report.parent.mkdir(parents=True, exist_ok=True)
        self.execution_report.write_text("\n".join(lines), encoding="utf-8")
        self.execution_report.with_suffix(".json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        logger.info("Execution report written to %s (+ .json)", self.execution_report)

    def _print_summary(self) -> None:
        print("\n" + "=" * 70 + "\nPIPELINE EXECUTION SUMMARY\n" + "=" * 70)
        print(f"Status: {self.status}")
        if self.error:
            print(f"Error: {self.error}")
        print(f"Duration: {self.end_time - self.start_time:.2f} seconds")
        print(f"Raw rows: {self.cleaning_report.get('raw_rows', 0)}, "
              f"clean: {self.cleaning_report.get('clean_rows', 0)}, "
              f"rejected: {self.cleaning_report.get('rejected_rows', 0)}")
        print(f"Validation: {self.validation_summary.get('passed', 0)} passed, "
              f"{self.validation_summary.get('failed', 0)} failed")
        print(f"Rows upserted: {self.rows_upserted}; table row count: {self.table_row_count}")
        print(f"Report: {self.execution_report} (+ .json)")
        print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="E-commerce Data Pipeline Automation")
    parser.add_argument("--raw-data", default=str(RAW_DATA), help="Path to raw data CSV")
    parser.add_argument("--db-url", help="SQLAlchemy URL (default: $DATABASE_URL or local SQLite)")
    parser.add_argument("--allow-validation-failures", action="store_true",
                        help="Upload even if validation checks fail")
    parser.add_argument("--max-rejection-pct", type=float, default=DEFAULT_MAX_REJECTION_PCT,
                        help="Fail validation if more than this %% of raw rows are rejected")
    parser.add_argument("--max-price", type=float, default=DEFAULT_MAX_PRICE,
                        help="Fail validation if any price exceeds this")
    args = parser.parse_args()

    setup_logging()
    pipeline = DataPipeline(
        raw_data=args.raw_data,
        db_url=args.db_url,
        allow_validation_failures=args.allow_validation_failures,
        max_rejection_pct=args.max_rejection_pct,
        max_price=args.max_price,
    )
    sys.exit(0 if pipeline.run_pipeline() else 1)


if __name__ == "__main__":
    main()
