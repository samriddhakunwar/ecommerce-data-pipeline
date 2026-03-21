# E-commerce Data Pipeline & Automation System

A production-ready, fully-automated data pipeline system that processes, cleans, validates, and delivers e-commerce product data. This project demonstrates **end-to-end backend development skills** including data processing, database management, and REST API design.

## Project Overview

This system simulates real-world data engineering challenges:

- Processing messy, real-world datasets
- Data quality validation and reporting
- Automated workflow orchestration
- RESTful API for data access
- Database management (SQLite, MySQL, PostgreSQL)

**Perfect for**: Job applications, portfolio building, learning data engineering

## Features

✅ **Automated Data Pipeline**

- Single command to process entire workflow: `python scripts/automate_pipeline.py`

✅ **Comprehensive Data Cleaning**

- Remove duplicates
- Handle missing values
- Standardize categories and names
- Validate and convert data types
- Date format standardization

✅ **Data Quality Validation**

- Automated quality checks
- Data integrity verification
- Generates detailed quality reports
- Identifies specific issues and counts

✅ **Database Management**

- Support for SQLite, MySQL, PostgreSQL
- Automatic schema creation
- Proper data type handling
- Transaction management

✅ **REST API Layer**

- FastAPI endpoints for data access
- Pagination support
- Category filtering
- Statistics endpoint
- Health checks

✅ **Comprehensive Documentation**

- Detailed workflow documentation
- Code comments and docstrings
- Professional README
- Usage examples

## Tech Stack

**Core Technologies**:

- Python 3.8+
- Pandas - Data manipulation
- SQLAlchemy - ORM and database management
- FastAPI - REST API framework
- SQLite/MySQL/PostgreSQL - Databases

**Additional Libraries**:

- NumPy - Numerical operations
- Uvicorn - ASGI server
- Python-multipart - File uploads

## Project Structure

```
ecommerce-data-pipeline/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
│
├── data/
│   ├── raw_products.csv               # Raw messy data (~1500 rows)
│   └── cleaned_products.csv           # Cleaned data (output)
│
├── scripts/
│   ├── clean_data.py                  # Data cleaning module
│   ├── validate_data.py               # Data validation module
│   ├── upload_to_db.py                # Database upload module
│   └── automate_pipeline.py           # Main orchestration script
│
├── database/
│   └── schema.sql                     # Database schema + views
│
├── api/
│   └── app.py                         # FastAPI application
│
├── reports/
│   ├── data_quality_report.csv        # Validation results
│   └── pipeline_execution_report.txt  # Pipeline run report
│
└── docs/
    └── workflow.md                    # Detailed workflow documentation
```

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/ecommerce-data-pipeline.git
cd ecommerce-data-pipeline
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### Option 1: Run Full Automated Pipeline

```bash
# Generate raw data
python generate_raw_data.py

# Run complete pipeline
python scripts/automate_pipeline.py
```

This will:

1. Clean the data
2. Validate quality
3. Upload to database
4. Generate reports

**Execution time**: ~5 seconds

### Option 2: Run Individual Steps

**Step 1: Data Cleaning**

```bash
python scripts/clean_data.py
```

Output: `data/cleaned_products.csv`

**Step 2: Data Validation**

```bash
python scripts/validate_data.py
```

Output: `reports/data_quality_report.csv`

**Step 3: Database Upload**

```bash
python scripts/upload_to_db.py
```

Output: `ecommerce.db` (SQLite database)

### Option 3: Use Different Database

```bash
# Use MySQL instead of SQLite
python scripts/automate_pipeline.py --db-type mysql
```

## API Usage

### Start API Server

```bash
cd api
uvicorn app:app --reload
```

Server runs at: `http://localhost:8000`

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Example API Calls

**Get All Products**

```bash
curl "http://localhost:8000/products?limit=10"
```

**Get Product by ID**

```bash
curl "http://localhost:8000/products/PROD_00001"
```

**Get Products by Category**

```bash
curl "http://localhost:8000/products/category/Electronics"
```

**Get Statistics**

```bash
curl "http://localhost:8000/stats"
```

**Health Check**

```bash
curl "http://localhost:8000/health"
```

## Data Pipeline Details

### Input Data Characteristics

- **Format**: CSV
- **Rows**: ~1500
- **Quality Issues**:
  - Missing values: 3-5%
  - Invalid prices: 10%
  - Negative stock: 5%
  - Duplicate rows: 5%
  - Inconsistent categories

### Output Data Characteristics

- **Format**: CSV + Database
- **Rows**: ~1200 (after cleaning)
- **Quality**: 100% valid
- **Data Types**: Properly converted
- **Uniqueness**: No duplicates

### Data Cleaning Steps

1. Remove duplicates
2. Remove rows with missing product names
3. Standardize category names
4. Convert prices to numeric (remove invalid)
5. Validate stock values (remove negative)
6. Parse and validate dates
7. Standardize supplier names

### Validation Checks

1. Missing values detection
2. Duplicate product ID detection
3. Price validity (positive numbers)
4. Stock validity (non-negative)
5. Category validation (allowed values)
6. Product name validation
7. Date format validation

## Database Schema

### Products Table

```sql
CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    supplier VARCHAR(255),
    last_updated DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Available Views

- `low_stock_products` - Products with stock < 10
- `products_by_category` - Category statistics
- `supplier_statistics` - Supplier metrics

## Performance

- **Data Cleaning**: < 1 second
- **Data Validation**: < 0.5 seconds
- **Database Upload**: < 2 seconds
- **Total Pipeline**: < 5 seconds
- **Data Throughput**: ~300 rows/second

## Code Quality

✅ **Clean Code**:

- Modular, reusable functions
- Comprehensive docstrings
- Descriptive variable names
- Professional formatting

✅ **Error Handling**:

- Try-except blocks
- Descriptive error messages
- Logging at all stages

✅ **Best Practices**:

- Separation of concerns
- DRY (Don't Repeat Yourself)
- SOLID principles
- Type hints

## Example Outputs

### Data Quality Report

```csv
check,column,status,details,count
Missing Values,product_id,PASS,No missing values,0
Category Validity,category,PASS,All categories valid,0
Price Validity,price,PASS,All prices valid,0
Stock Validity,stock,PASS,All stock valid,0
```

### Pipeline Execution Report

```
DATA PIPELINE EXECUTION REPORT
======================================================================

Execution Time: 2024-01-15 10:30:45
Pipeline Duration: 4.23 seconds

STATUS: SUCCESS

FILES PROCESSED:
- Raw Data: data/raw_products.csv
- Cleaned Data: data/cleaned_products.csv
- Validation Report: reports/data_quality_report.csv

DATABASE:
- Type: sqlite
- Table: products
```

## Configuration

### Use MySQL Database

Update connection string in `upload_to_db.py`:

```python
connection_string = "mysql+pymysql://user:password@localhost/ecommerce"
```

### Adjust Data Generation

In `generate_raw_data.py`, modify:

```python
num_rows = 1500  # Change dataset size
```

## Troubleshooting

**Error: Module not found**

```bash
pip install --upgrade -r requirements.txt
```

**Database locked**

- Close all database connections
- Try again

**API port already in use**

```bash
uvicorn app:app --port 8001 --reload
```

## Learning Outcomes

This project demonstrates:

- Python data processing with Pandas
- Database design and management
- SQL schema creation and optimization
- REST API development with FastAPI
- Data quality and validation
- Automated workflow orchestration
- Error handling and logging
- Documentation and best practices

## Next Steps / Enhancements

1. **Real-time Scheduling**: Use Apache Airflow or Celery
2. **Advanced Monitoring**: Add Prometheus metrics
3. **Data Profiling**: Generate statistical profiles
4. **Version Control**: Track data changes over time
5. **Incremental Updates**: Only process new/changed data
6. **Web Dashboard**: Visualize pipeline metrics
7. **Authentication**: Add API authentication
8. **Docker**: Containerize the application

## GitHub Repository

```
https://github.com/YOUR_USERNAME/ecommerce-data-pipeline
```

Replace `YOUR_USERNAME` with your actual GitHub username.

## Portfolio Use

**Showcase this project to demonstrate**:

- Data engineering capabilities
- Backend development skills
- Database management knowledge
- API design and implementation
- Code quality and best practices
- Problem-solving abilities

**Perfect for**: Job applications, freelance projects, interviews

## Support & Contributing

Found an issue? Have a suggestion?

1. Create an issue in the repository
2. Submit a pull request with improvements
3. Document your changes clearly

## License

This project is open source and available for educational and portfolio purposes.

## Author

Created as a portfolio data engineering project demonstrating:

- Full-stack data pipeline development
- Production-ready code quality
- Real-world problem solving
- Professional documentation

---

**Version**: 1.0
**Last Updated**: 2024
**Status**: Production Ready

**Get Started**: `python scripts/automate_pipeline.py`
