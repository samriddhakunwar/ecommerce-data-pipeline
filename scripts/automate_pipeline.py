"""
Automation Pipeline Orchestrator
Orchestrates the entire data pipeline process
Run: python automate_pipeline.py
"""
import sys
import time
import logging
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from clean_data import DataCleaner
from validate_data import DataValidator
from upload_to_db import DatabaseUploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataPipeline:
    """Orchestrate entire data pipeline"""

    def __init__(self, raw_data='data/raw_products.csv', db_type='sqlite'):
        """Initialize pipeline"""
        self.raw_data = raw_data
        self.cleaned_data = 'data/cleaned_products.csv'
        self.validation_report = 'reports/data_quality_report.csv'
        self.db_type = db_type
        self.start_time = None
        self.end_time = None

    def run_pipeline(self):
        """Execute full pipeline"""
        try:
            self.start_time = time.time()

            print("\n" + "="*70)
            print("E-COMMERCE DATA PIPELINE AUTOMATION")
            print("="*70)

            # Step 1: Data Cleaning
            print("\n[STEP 1/4] CLEANING DATA...")
            self._step_cleaning()
            print("[OK] Data cleaning complete")

            # Step 2: Data Validation
            print("\n[STEP 2/4] VALIDATING DATA...")
            self._step_validation()
            print("[OK] Data validation complete")

            # Step 3: Database Upload
            print("\n[STEP 3/4] UPLOADING TO DATABASE...")
            self._step_database_upload()
            print("[OK] Database upload complete")

            # Record end time before report generation (report uses this)
            self.end_time = time.time()

            # Step 4: Generate Report
            print("\n[STEP 4/4] GENERATING REPORT...")
            self._step_generate_report()
            print("[OK] Report generated")

            self._print_summary()

            return True

        except Exception as e:
            if self.end_time is None:
                self.end_time = time.time()
            logger.error(f"Pipeline execution failed: {e}")
            print(f"\n[ERROR] Pipeline failed: {e}")
            return False

    def _step_cleaning(self):
        """Execute data cleaning step"""
        try:
            cleaner = DataCleaner(self.raw_data)
            cleaner.run_all_cleaning()
            cleaner.save_cleaned_data(self.cleaned_data)
            logger.info("Data cleaning step completed successfully")
        except Exception as e:
            logger.error(f"Cleaning step failed: {e}")
            raise

    def _step_validation(self):
        """Execute data validation step"""
        try:
            validator = DataValidator(self.cleaned_data)
            validator.run_all_validations()
            validator.save_report(self.validation_report)
            logger.info("Data validation step completed successfully")
        except Exception as e:
            logger.error(f"Validation step failed: {e}")
            raise

    def _step_database_upload(self):
        """Execute database upload step"""
        try:
            uploader = DatabaseUploader(db_type=self.db_type)
            uploader.connect()
            uploader.create_schema()
            uploader.upload_data(self.cleaned_data, if_exists='replace')
            uploader.verify_upload()
            uploader.get_statistics()
            uploader.close()
            logger.info("Database upload step completed successfully")
        except Exception as e:
            logger.error(f"Database upload step failed: {e}")
            raise

    def _step_generate_report(self):
        """Generate execution report"""
        try:
            report_content = f"""
DATA PIPELINE EXECUTION REPORT
{'='*70}

Execution Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}
Pipeline Duration: {self.end_time - self.start_time:.2f} seconds

FILES PROCESSED:
- Raw Data: {self.raw_data}
- Cleaned Data: {self.cleaned_data}
- Validation Report: {self.validation_report}

DATABASE:
- Type: {self.db_type}
- Table: products

STATUS: SUCCESS

NEXT STEPS:
1. Review data quality report in {self.validation_report}
2. Query products from database using SQL or API
3. Monitor data pipeline regularly
"""
            with open('reports/pipeline_execution_report.txt', 'w') as f:
                f.write(report_content)

            logger.info("Execution report generated")

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise

    def _print_summary(self):
        """Print pipeline summary"""
        duration = self.end_time - self.start_time
        print("\n" + "="*70)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*70)
        print(f"Status: SUCCESS")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}")
        print(f"End Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.end_time))}")
        print(f"\nOutput Files Generated:")
        print(f"  - {self.cleaned_data}")
        print(f"  - {self.validation_report}")
        print(f"  - reports/pipeline_execution_report.txt")
        print(f"  - ecommerce.db (SQLite database)")
        print("="*70 + "\n")


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='E-commerce Data Pipeline Automation')
    parser.add_argument('--db-type', default='sqlite', choices=['sqlite', 'mysql', 'postgresql'],
                       help='Database type (default: sqlite)')
    parser.add_argument('--raw-data', default='data/raw_products.csv',
                       help='Path to raw data CSV file')

    args = parser.parse_args()

    pipeline = DataPipeline(raw_data=args.raw_data, db_type=args.db_type)
    success = pipeline.run_pipeline()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
