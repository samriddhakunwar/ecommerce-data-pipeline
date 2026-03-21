"""
Database Upload Module
Upload cleaned data to SQL database
Supports SQLite, MySQL, and PostgreSQL
"""
import pandas as pd
import sqlite3
import logging
from sqlalchemy import create_engine, inspect, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseUploader:
    """Handle database operations for product data"""

    def __init__(self, db_type='sqlite', db_path='ecommerce.db'):
        """
        Initialize database uploader

        db_type: 'sqlite', 'mysql', or 'postgresql'
        db_path: path for sqlite or connection string for others
        """
        self.db_type = db_type
        self.db_path = db_path
        self.engine = None
        self.connection = None

    def connect(self):
        """Establish database connection"""
        try:
            if self.db_type == 'sqlite':
                connection_string = f'sqlite:///{self.db_path}'
            elif self.db_type == 'mysql':
                connection_string = self.db_path
            elif self.db_type == 'postgresql':
                connection_string = self.db_path
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")

            self.engine = create_engine(connection_string)
            logger.info(f"Connected to {self.db_type} database")
            return self.engine
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def create_schema(self):
        """Create products table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS products (
            product_id VARCHAR(50) PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock INT NOT NULL,
            supplier VARCHAR(255),
            last_updated DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
            logger.info("Products table created or already exists")
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            raise

    def upload_data(self, csv_file, table_name='products', if_exists='replace'):
        """
        Upload cleaned CSV data to database

        if_exists: 'fail', 'replace', or 'append'
        """
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Loading {len(df)} rows from {csv_file}")

            # Convert date column
            df['last_updated'] = pd.to_datetime(df['last_updated'])

            # Upload to database
            df.to_sql(table_name, self.engine, if_exists=if_exists, index=False)
            logger.info(f"Successfully uploaded {len(df)} rows to {table_name} table")
            return len(df)

        except Exception as e:
            logger.error(f"Error uploading data: {e}")
            raise

    def verify_upload(self, table_name='products'):
        """Verify data was uploaded correctly"""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            if table_name not in tables:
                logger.error(f"Table {table_name} does not exist")
                return False

            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = result.scalar()

            logger.info(f"Table {table_name} contains {row_count} rows")
            return True

        except Exception as e:
            logger.error(f"Error verifying upload: {e}")
            return False

    def get_statistics(self, table_name='products'):
        """Get basic statistics from uploaded data"""
        try:
            df = pd.read_sql_table(table_name, self.engine)
            print("\n" + "="*50)
            print("DATABASE STATISTICS")
            print("="*50)
            print(f"Total products: {len(df)}")
            print(f"Categories: {df['category'].nunique()}")
            print(f"Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
            print(f"Average price: ${df['price'].mean():.2f}")
            print(f"Total stock: {df['stock'].sum():,}")
            print(f"Suppliers: {df['supplier'].nunique()}")

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


def main(db_type='sqlite', csv_file='data/cleaned_products.csv'):
    """Main execution"""
    logger.info("="*50)
    logger.info("DATABASE UPLOAD PROCESS")
    logger.info("="*50)

    uploader = DatabaseUploader(db_type=db_type)
    uploader.connect()
    uploader.create_schema()
    uploader.upload_data(csv_file, if_exists='replace')
    uploader.verify_upload()
    uploader.get_statistics()
    uploader.close()

    logger.info("="*50)
    logger.info("DATABASE UPLOAD COMPLETE")
    logger.info("="*50)


if __name__ == '__main__':
    main()
