"""
Data Validation Module
Performs comprehensive data quality checks
"""
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataValidator:
    """Validate cleaned product data"""

    def __init__(self, input_file):
        """Initialize with cleaned data file"""
        self.input_file = input_file
        self.df = None
        self.validation_report = []

    def load_data(self):
        """Load cleaned CSV data"""
        try:
            self.df = pd.read_csv(self.input_file)
            logger.info(f"Loaded {len(self.df)} rows from {self.input_file}")
            return self.df
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def check_missing_values(self):
        """Check for missing values"""
        missing = self.df.isnull().sum()
        for col, count in missing.items():
            if count > 0:
                self.validation_report.append({
                    'check': 'Missing Values',
                    'column': col,
                    'status': 'FAIL',
                    'details': f'{count} missing values',
                    'count': count
                })
                logger.warning(f"Missing values in {col}: {count}")
            else:
                self.validation_report.append({
                    'check': 'Missing Values',
                    'column': col,
                    'status': 'PASS',
                    'details': 'No missing values',
                    'count': 0
                })

    def check_duplicate_product_ids(self):
        """Check for duplicate product IDs"""
        duplicates = self.df['product_id'].duplicated().sum()
        status = 'FAIL' if duplicates > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Duplicate Product IDs',
            'column': 'product_id',
            'status': status,
            'details': f'{duplicates} duplicate IDs found' if duplicates > 0 else 'No duplicates',
            'count': duplicates
        })
        logger.warning(f"Duplicate product IDs: {duplicates}") if duplicates > 0 else None

    def check_price_validity(self):
        """Check if all prices are positive"""
        invalid_prices = (self.df['price'] <= 0).sum()
        status = 'FAIL' if invalid_prices > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Price Validity',
            'column': 'price',
            'status': status,
            'details': f'{invalid_prices} negative/zero prices' if invalid_prices > 0 else 'All prices valid',
            'count': invalid_prices
        })

    def check_stock_validity(self):
        """Check if stock values are non-negative"""
        invalid_stock = (self.df['stock'] < 0).sum()
        status = 'FAIL' if invalid_stock > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Stock Validity',
            'column': 'stock',
            'status': status,
            'details': f'{invalid_stock} negative stock values' if invalid_stock > 0 else 'All stock valid',
            'count': invalid_stock
        })

    def check_category_validity(self):
        """Check if categories are valid"""
        valid_categories = ['Electronics', 'Accessories', 'Storage', 'Peripherals', 'Networking', 'Audio', 'Computing', 'Other']
        invalid_categories = self.df[~self.df['category'].isin(valid_categories)].shape[0]
        status = 'FAIL' if invalid_categories > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Category Validity',
            'column': 'category',
            'status': status,
            'details': f'{invalid_categories} invalid categories' if invalid_categories > 0 else 'All categories valid',
            'count': invalid_categories
        })

    def check_product_names(self):
        """Check for empty product names"""
        empty_names = (self.df['product_name'].str.strip() == '').sum()
        status = 'FAIL' if empty_names > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Product Name Validity',
            'column': 'product_name',
            'status': status,
            'details': f'{empty_names} empty product names' if empty_names > 0 else 'All product names valid',
            'count': empty_names
        })

    def check_date_format(self):
        """Check if dates are in valid format"""
        self.df['last_updated'] = pd.to_datetime(self.df['last_updated'], errors='coerce')
        invalid_dates = self.df['last_updated'].isnull().sum()
        status = 'FAIL' if invalid_dates > 0 else 'PASS'
        self.validation_report.append({
            'check': 'Date Format',
            'column': 'last_updated',
            'status': status,
            'details': f'{invalid_dates} invalid dates' if invalid_dates > 0 else 'All dates valid',
            'count': invalid_dates
        })

    def run_all_validations(self):
        """Execute all validation checks"""
        logger.info("="*50)
        logger.info("STARTING DATA VALIDATION")
        logger.info("="*50)

        self.load_data()
        self.check_missing_values()
        self.check_duplicate_product_ids()
        self.check_price_validity()
        self.check_stock_validity()
        self.check_category_validity()
        self.check_product_names()
        self.check_date_format()

        logger.info("="*50)
        logger.info("DATA VALIDATION COMPLETE")
        logger.info("="*50)

    def save_report(self, output_file):
        """Save validation report to CSV"""
        report_df = pd.DataFrame(self.validation_report)
        report_df.to_csv(output_file, index=False)
        logger.info(f"Validation report saved to: {output_file}")

    def print_summary(self):
        """Print validation summary"""
        report_df = pd.DataFrame(self.validation_report)
        passed = (report_df['status'] == 'PASS').sum()
        failed = (report_df['status'] == 'FAIL').sum()

        print("\n" + "="*50)
        print("VALIDATION SUMMARY")
        print("="*50)
        print(f"Total Checks: {len(report_df)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print("\nDetailed Report:")
        print(report_df.to_string(index=False))


def main():
    """Main execution"""
    validator = DataValidator('data/cleaned_products.csv')
    validator.run_all_validations()
    validator.save_report('reports/data_quality_report.csv')
    validator.print_summary()


if __name__ == '__main__':
    main()
