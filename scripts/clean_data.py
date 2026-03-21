"""
Data Cleaning Module
Handles all data quality and transformation tasks
"""
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCleaner:
    """Clean and standardize product data"""

    def __init__(self, input_file):
        """Initialize with raw data file"""
        self.input_file = input_file
        self.df = None
        self.cleaning_report = {}

    def load_data(self):
        """Load raw CSV data"""
        try:
            self.df = pd.read_csv(self.input_file)
            logger.info(f"Loaded {len(self.df)} rows from {self.input_file}")
            return self.df
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def remove_duplicates(self):
        """Remove duplicate rows"""
        initial_count = len(self.df)
        self.df = self.df.drop_duplicates()
        duplicates_removed = initial_count - len(self.df)
        self.cleaning_report['duplicates_removed'] = duplicates_removed
        logger.info(f"Removed {duplicates_removed} duplicate rows")

    def clean_product_names(self):
        """Remove rows with missing product names"""
        initial_count = len(self.df)
        self.df = self.df[self.df['product_name'].notna()]
        self.cleaning_report['missing_names_removed'] = initial_count - len(self.df)
        logger.info(f"Removed {self.cleaning_report['missing_names_removed']} rows with missing product names")

    def standardize_categories(self):
        """Standardize category names (lowercase, capitalize first letter)"""
        category_map = {
            'electronics': 'Electronics',
            'ELECTRONICS': 'Electronics',
            'accessories': 'Accessories',
            'peripherals': 'Peripherals',
            'networking': 'Networking',
            'audio': 'Audio',
            'storage': 'Storage',
            'STORAGE': 'Storage',
            'computing': 'Computing',
        }

        self.df['category'] = self.df['category'].str.lower().map(
            lambda x: category_map.get(x, 'Other')
        )
        logger.info("Standardized category names")

    def clean_prices(self):
        """Convert prices to numeric, remove invalid values"""
        initial_count = len(self.df)

        # Convert to numeric, coerce errors to NaN
        self.df['price'] = pd.to_numeric(self.df['price'], errors='coerce')

        # Remove rows where price is invalid (NaN or negative)
        self.df = self.df[
            (self.df['price'].notna()) &
            (self.df['price'] > 0)
        ]

        invalid_prices = initial_count - len(self.df)
        self.cleaning_report['invalid_prices_removed'] = invalid_prices
        logger.info(f"Removed {invalid_prices} rows with invalid prices")

    def clean_stock(self):
        """Ensure stock values are valid (non-negative integers)"""
        initial_count = len(self.df)

        # Convert to numeric
        self.df['stock'] = pd.to_numeric(self.df['stock'], errors='coerce')

        # Remove rows with missing or negative stock
        self.df = self.df[
            (self.df['stock'].notna()) &
            (self.df['stock'] >= 0)
        ]

        # Convert to int
        self.df['stock'] = self.df['stock'].astype(int)

        invalid_stock = initial_count - len(self.df)
        self.cleaning_report['invalid_stock_removed'] = invalid_stock
        logger.info(f"Removed {invalid_stock} rows with invalid stock")

    def clean_dates(self):
        """Standardize and validate dates"""
        def parse_date(date_str):
            """Try multiple date formats"""
            if pd.isna(date_str):
                return pd.NaT

            formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
            for fmt in formats:
                try:
                    return pd.to_datetime(date_str, format=fmt)
                except:
                    continue
            return pd.NaT

        self.df['last_updated'] = self.df['last_updated'].apply(parse_date)

        # Remove invalid dates
        initial_count = len(self.df)
        self.df = self.df[self.df['last_updated'].notna()]
        invalid_dates = initial_count - len(self.df)
        self.cleaning_report['invalid_dates_removed'] = invalid_dates
        logger.info(f"Removed {invalid_dates} rows with invalid dates")

    def clean_supplier(self):
        """Clean and standardize supplier names"""
        self.df['supplier'] = self.df['supplier'].str.strip()
        self.df['supplier'] = self.df['supplier'].fillna('Unknown')
        logger.info("Cleaned supplier names")

    def run_all_cleaning(self):
        """Execute all cleaning steps"""
        logger.info("="*50)
        logger.info("STARTING DATA CLEANING PIPELINE")
        logger.info("="*50)

        self.load_data()
        self.remove_duplicates()
        self.clean_product_names()
        self.standardize_categories()
        self.clean_prices()
        self.clean_stock()
        self.clean_dates()
        self.clean_supplier()

        logger.info("="*50)
        logger.info("DATA CLEANING COMPLETE")
        logger.info("="*50)
        logger.info(f"Final dataset size: {len(self.df)} rows")

    def save_cleaned_data(self, output_file):
        """Save cleaned data to CSV"""
        self.df.to_csv(output_file, index=False)
        logger.info(f"Cleaned data saved to: {output_file}")

    def get_report(self):
        """Return cleaning report"""
        return self.cleaning_report


def main():
    """Main execution"""
    cleaner = DataCleaner('data/raw_products.csv')
    cleaner.run_all_cleaning()
    cleaner.save_cleaned_data('data/cleaned_products.csv')

    print("\n" + "="*50)
    print("CLEANING SUMMARY")
    print("="*50)
    report = cleaner.get_report()
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == '__main__':
    main()
