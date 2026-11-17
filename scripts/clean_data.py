"""
Data Cleaning Module

Cleans raw product data. Every row that is removed is kept, with a
`rejection_reason`, so it can be written to data/rejected_products.csv.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import CLEANED_DATA, RAW_DATA, REJECTED_DATA, setup_logging

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "product_id", "product_name", "category", "price", "stock", "supplier", "last_updated",
]

# Keys are lowercase: categories are normalized with .str.strip().str.lower() first.
CATEGORY_MAP = {
    "electronics": "Electronics",
    "accessories": "Accessories",
    "storage": "Storage",
    "peripherals": "Peripherals",
    "networking": "Networking",
    "audio": "Audio",
    "computing": "Computing",
}
VALID_CATEGORIES = [*CATEGORY_MAP.values(), "Other"]

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]


class DataCleaner:
    """Clean and standardize product data."""

    def __init__(self, input_file: str | Path | None = None, df: pd.DataFrame | None = None):
        """Clean either a CSV file (`input_file`) or an in-memory DataFrame (`df`)."""
        if input_file is None and df is None:
            raise ValueError("Provide input_file or df")
        self.input_file = input_file
        self.df: pd.DataFrame | None = None if df is None else df.reset_index(drop=True)
        self.cleaning_report: dict[str, int] = {}
        self._rejected: list[pd.DataFrame] = []

    # --- helpers -----------------------------------------------------------------
    def _reject(self, mask: pd.Series, reason: str) -> int:
        """Move rows matching `mask` out of self.df into the rejected set."""
        removed = self.df[mask].copy()
        if not removed.empty:
            removed["rejection_reason"] = reason
            self._rejected.append(removed)
        self.df = self.df[~mask].copy()
        return len(removed)

    @property
    def rejected(self) -> pd.DataFrame:
        """All rejected rows with a rejection_reason column."""
        if not self._rejected:
            return pd.DataFrame(columns=[*REQUIRED_COLUMNS, "rejection_reason"])
        return pd.concat(self._rejected, ignore_index=True)

    # --- steps -------------------------------------------------------------------
    def load_data(self) -> pd.DataFrame:
        """Load raw CSV data as strings, so original values survive into rejects."""
        if self.df is None:
            self.df = pd.read_csv(self.input_file, dtype=str)
            logger.info("Loaded %d rows from %s", len(self.df), self.input_file)
        missing = [c for c in REQUIRED_COLUMNS if c not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.cleaning_report["raw_rows"] = len(self.df)
        return self.df

    def strip_whitespace(self) -> None:
        """Strip whitespace on all string columns; blank strings become missing."""
        for col in self.df.columns:
            if self.df[col].dtype == object:
                self.df[col] = self.df[col].str.strip().replace("", pd.NA)

    def clean_product_ids(self) -> None:
        """Remove rows without a product_id (it's the primary key)."""
        n = self._reject(self.df["product_id"].isna(), "missing_product_id")
        self.cleaning_report["missing_ids_removed"] = n
        logger.info("Removed %d rows with missing product_id", n)

    def clean_product_names(self) -> None:
        """Remove rows with missing or blank product names."""
        n = self._reject(self.df["product_name"].isna(), "missing_product_name")
        self.cleaning_report["missing_names_removed"] = n
        logger.info("Removed %d rows with missing product names", n)

    def standardize_categories(self) -> None:
        """Map categories to canonical names; unknown or missing become 'Other'."""
        normalized = self.df["category"].str.strip().str.lower()
        mapped = normalized.map(CATEGORY_MAP)
        other = int(mapped.isna().sum())
        self.df["category"] = mapped.fillna("Other")
        self.cleaning_report["categories_mapped_to_other"] = other
        logger.info("Standardized categories; %d rows mapped to 'Other'", other)

    def clean_prices(self) -> None:
        """Convert prices to numeric, reject missing/non-numeric/non-positive, round to 2dp."""
        price = pd.to_numeric(self.df["price"], errors="coerce")
        self.df["price"] = price
        n = self._reject(price.isna() | (price <= 0), "invalid_price")
        self.df["price"] = self.df["price"].round(2)
        self.cleaning_report["invalid_prices_removed"] = n
        logger.info("Removed %d rows with invalid prices", n)

    def clean_stock(self) -> None:
        """Reject missing, negative or fractional stock; cast to int."""
        stock = pd.to_numeric(self.df["stock"], errors="coerce")
        self.df["stock"] = stock
        n = self._reject(stock.isna() | (stock < 0) | (stock % 1 != 0), "invalid_stock")
        self.df["stock"] = self.df["stock"].astype(int)
        self.cleaning_report["invalid_stock_removed"] = n
        logger.info("Removed %d rows with invalid stock", n)

    def clean_dates(self) -> None:
        """Parse dates trying each known format (vectorized); reject unparseable ones."""
        raw = self.df["last_updated"]
        parsed = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
        for fmt in DATE_FORMATS:
            parsed = parsed.fillna(pd.to_datetime(raw, format=fmt, errors="coerce"))
        self.df["last_updated"] = parsed
        n = self._reject(parsed.isna(), "invalid_date")
        self.cleaning_report["invalid_dates_removed"] = n
        logger.info("Removed %d rows with invalid dates", n)

    def remove_duplicates(self) -> None:
        """Keep one row per product_id: the one with the latest last_updated.

        Ties keep the row that appears last in the input. Runs after the validity
        filters, so a valid row is never dropped in favour of an invalid one.
        """
        ordered = self.df.sort_values("last_updated", kind="mergesort")
        dup_mask = ordered.duplicated("product_id", keep="last").reindex(self.df.index)
        n = self._reject(dup_mask, "duplicate_product_id")
        self.cleaning_report["duplicates_removed"] = n
        logger.info("Removed %d duplicate product_id rows", n)

    def clean_supplier(self) -> None:
        """Fill missing suppliers with 'Unknown'."""
        self.df["supplier"] = self.df["supplier"].fillna("Unknown")

    def run_all_cleaning(self) -> pd.DataFrame:
        """Execute all cleaning steps and return the cleaned DataFrame."""
        logger.info("Starting data cleaning")
        self.load_data()
        self.strip_whitespace()
        self.clean_product_ids()
        self.clean_product_names()
        self.standardize_categories()
        self.clean_prices()
        self.clean_stock()
        self.clean_dates()
        self.remove_duplicates()
        self.clean_supplier()
        self.df = self.df[REQUIRED_COLUMNS].reset_index(drop=True)
        self.cleaning_report["clean_rows"] = len(self.df)
        self.cleaning_report["rejected_rows"] = sum(len(r) for r in self._rejected)
        logger.info(
            "Cleaning complete: %d clean rows, %d rejected",
            self.cleaning_report["clean_rows"], self.cleaning_report["rejected_rows"],
        )
        return self.df

    def save_cleaned_data(self, output_file: str | Path) -> None:
        """Save cleaned data to CSV (dates as YYYY-MM-DD)."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(output_file, index=False, date_format="%Y-%m-%d")
        logger.info("Cleaned data saved to: %s", output_file)

    def save_rejected_data(self, output_file: str | Path) -> None:
        """Save every rejected row with its rejection_reason."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        self.rejected.to_csv(output_file, index=False, date_format="%Y-%m-%d")
        logger.info("Rejected rows saved to: %s", output_file)

    def get_report(self) -> dict[str, int]:
        """Return the cleaning report (per-step counts)."""
        return self.cleaning_report


def main() -> None:
    setup_logging()
    cleaner = DataCleaner(RAW_DATA)
    cleaner.run_all_cleaning()
    cleaner.save_cleaned_data(CLEANED_DATA)
    cleaner.save_rejected_data(REJECTED_DATA)

    print("\n" + "=" * 50)
    print("CLEANING SUMMARY")
    print("=" * 50)
    for key, value in cleaner.get_report().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
