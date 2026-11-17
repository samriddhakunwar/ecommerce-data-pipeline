"""
Data Validation Module

Runs quality checks on cleaned product data. Any FAIL makes `has_failures`
true, which the pipeline uses as a quality gate before the database upload.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from clean_data import REQUIRED_COLUMNS, VALID_CATEGORIES
from config import CLEANED_DATA, QUALITY_REPORT, setup_logging

logger = logging.getLogger(__name__)

DEFAULT_MAX_PRICE = 100_000.0
DEFAULT_MAX_REJECTION_PCT = 40.0


class DataValidator:
    """Validate cleaned product data."""

    def __init__(
        self,
        input_file: str | Path | None = None,
        df: pd.DataFrame | None = None,
        raw_row_count: int | None = None,
        max_price: float = DEFAULT_MAX_PRICE,
        max_rejection_pct: float = DEFAULT_MAX_REJECTION_PCT,
    ) -> None:
        """
        raw_row_count: rows before cleaning; enables the rejection-rate check.
        max_price: prices above this fail the sanity check.
        max_rejection_pct: fail if more than this % of raw rows were rejected.
        """
        if input_file is None and df is None:
            raise ValueError("Provide input_file or df")
        self.input_file = input_file
        self.df: pd.DataFrame | None = df
        self.raw_row_count = raw_row_count
        self.max_price = max_price
        self.max_rejection_pct = max_rejection_pct
        self.validation_report: list[dict] = []

    def _record(self, check: str, column: str, count: int, fail_details: str, ok: str) -> None:
        failed = count > 0
        self.validation_report.append({
            "check": check,
            "column": column,
            "status": "FAIL" if failed else "PASS",
            "details": fail_details if failed else ok,
            "count": int(count),
        })
        if failed:
            logger.warning("%s failed on %s: %s", check, column, fail_details)

    def load_data(self) -> pd.DataFrame:
        """Load cleaned CSV data (unless a DataFrame was passed in)."""
        if self.df is None:
            self.df = pd.read_csv(self.input_file, dtype={"product_id": str})
            logger.info("Loaded %d rows from %s", len(self.df), self.input_file)
        return self.df

    def check_required_columns(self) -> bool:
        """Fail if any required column is absent. Returns True if all present."""
        missing = [c for c in REQUIRED_COLUMNS if c not in self.df.columns]
        self._record("Required Columns", ",".join(missing) or "*", len(missing),
                     f"missing columns: {missing}", "All required columns present")
        return not missing

    def check_missing_values(self) -> None:
        for col, count in self.df[REQUIRED_COLUMNS].isna().sum().items():
            self._record("Missing Values", col, count, f"{count} missing values",
                         "No missing values")

    def check_duplicate_product_ids(self) -> None:
        n = self.df["product_id"].duplicated().sum()
        self._record("Duplicate Product IDs", "product_id", n, f"{n} duplicate IDs found",
                     "No duplicates")

    def check_price_validity(self) -> None:
        price = pd.to_numeric(self.df["price"], errors="coerce")
        n = (price.isna() | (price <= 0)).sum()
        self._record("Price Validity", "price", n, f"{n} missing/non-numeric/non-positive prices",
                     "All prices valid")

    def check_price_upper_bound(self) -> None:
        price = pd.to_numeric(self.df["price"], errors="coerce")
        n = (price > self.max_price).sum()
        self._record("Price Upper Bound", "price", n, f"{n} prices above {self.max_price:,.2f}",
                     f"All prices <= {self.max_price:,.2f}")

    def check_stock_validity(self) -> None:
        stock = pd.to_numeric(self.df["stock"], errors="coerce")
        n = (stock.isna() | (stock < 0)).sum()
        self._record("Stock Validity", "stock", n, f"{n} missing/negative stock values",
                     "All stock valid")

    def check_category_validity(self) -> None:
        n = (~self.df["category"].isin(VALID_CATEGORIES)).sum()
        self._record("Category Validity", "category", n, f"{n} invalid categories",
                     "All categories valid")

    def check_product_names(self) -> None:
        names = self.df["product_name"]
        n = (names.isna() | (names.astype(str).str.strip() == "")).sum()
        self._record("Product Name Validity", "product_name", n,
                     f"{n} missing/empty product names", "All product names valid")

    def check_date_format(self) -> None:
        """Check dates parse as YYYY-MM-DD (does not modify self.df)."""
        parsed = pd.to_datetime(self.df["last_updated"], format="%Y-%m-%d", errors="coerce")
        n = parsed.isna().sum()
        self._record("Date Format", "last_updated", n, f"{n} invalid dates", "All dates valid")

    def check_rejection_rate(self) -> None:
        """Fail if too many raw rows were rejected during cleaning."""
        if not self.raw_row_count:
            return
        rejected = self.raw_row_count - len(self.df)
        pct = 100.0 * rejected / self.raw_row_count
        over = pct > self.max_rejection_pct
        self._record(
            "Rejection Rate", "*", rejected if over else 0,
            f"{pct:.1f}% of raw rows rejected (limit {self.max_rejection_pct:.1f}%)",
            f"{pct:.1f}% of raw rows rejected (limit {self.max_rejection_pct:.1f}%)",
        )

    def run_all_validations(self) -> list[dict]:
        """Execute all checks and return the report rows."""
        logger.info("Starting data validation")
        self.load_data()
        self.validation_report = []
        if self.check_required_columns():
            self.check_missing_values()
            self.check_duplicate_product_ids()
            self.check_price_validity()
            self.check_price_upper_bound()
            self.check_stock_validity()
            self.check_category_validity()
            self.check_product_names()
            self.check_date_format()
            self.check_rejection_rate()
        s = self.summary()
        logger.info("Validation complete: %d passed, %d failed", s["passed"], s["failed"])
        return self.validation_report

    @property
    def has_failures(self) -> bool:
        return any(r["status"] == "FAIL" for r in self.validation_report)

    @property
    def failed_checks(self) -> list[str]:
        return [f"{r['check']} ({r['column']})" for r in self.validation_report
                if r["status"] == "FAIL"]

    def summary(self) -> dict[str, int]:
        passed = sum(r["status"] == "PASS" for r in self.validation_report)
        return {"total": len(self.validation_report), "passed": passed,
                "failed": len(self.validation_report) - passed}

    def save_report(self, output_file: str | Path) -> None:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.validation_report).to_csv(output_file, index=False)
        logger.info("Validation report saved to: %s", output_file)

    def print_summary(self) -> None:
        s = self.summary()
        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)
        print(f"Total Checks: {s['total']}\nPassed: {s['passed']}\nFailed: {s['failed']}")
        print("\nDetailed Report:")
        print(pd.DataFrame(self.validation_report).to_string(index=False))


def main() -> None:
    setup_logging()
    validator = DataValidator(CLEANED_DATA)
    validator.run_all_validations()
    validator.save_report(QUALITY_REPORT)
    validator.print_summary()
    raise SystemExit(1 if validator.has_failures else 0)


if __name__ == "__main__":
    main()
