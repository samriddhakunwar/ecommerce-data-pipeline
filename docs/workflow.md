# Data Pipeline Workflow

## Overview

The E-commerce Data Pipeline is an automated system that processes raw product data from multiple sources, cleans and validates it, stores it in a relational database, and provides API access for consumption.

## Architecture Diagram

```
Raw Data (CSV)
    ↓
[Data Cleaning Module]
    - Remove duplicates
    - Handle missing values
    - Standardize categories
    - Convert data types
    ↓
Cleaned Data (CSV)
    ↓
[Data Validation Module]
    - Check data quality
    - Validate integrity
    - Generate quality report
    ↓
[Database Upload Module]
    - Create schema
    - Insert data
    - Verify upload
    ↓
SQLite/MySQL/PostgreSQL Database
    ↓
[REST API Layer]
    - GET endpoints
    - Health checks
    - Statistics
```

## Step-by-Step Workflow

### Step 1: Data Cleaning (`clean_data.py`)

**Purpose**: Transform raw, messy data into consistent, usable format

**Operations**:

1. **Load Raw Data**: Read CSV with potential quality issues
2. **Remove Duplicates**: Identify and eliminate duplicate rows based on all columns
3. **Clean Product Names**: Remove rows with missing or invalid product names
4. **Standardize Categories**: Map category names to standard values
   - Electronics, Accessories, Storage, Peripherals, Networking, Audio, Computing
5. **Clean Prices**:
   - Convert to numeric values
   - Remove negative prices
   - Remove rows with invalid prices
6. **Clean Stock**:
   - Validate stock is non-negative integer
   - Remove rows with invalid stock values
7. **Standardize Dates**:
   - Parse multiple date formats
   - Remove invalid dates
   - Convert to ISO format
8. **Clean Suppliers**: Standardize supplier names, fill missing values

**Input**: `data/raw_products.csv`
**Output**: `data/cleaned_products.csv`

**Typical Data Issues Handled**:

- Missing values (~3-5%)
- Invalid prices (~10%)
- Negative stock (~5%)
- Duplicate rows (~5%)
- Inconsistent category names
- Date format variations

### Step 2: Data Validation (`validate_data.py`)

**Purpose**: Ensure data quality and generate validation reports

**Validation Checks**:

1. **Missing Values**: Check each column for null/missing data
2. **Duplicate Product IDs**: Ensure product_id uniqueness
3. **Price Validity**: Verify all prices > 0
4. **Stock Validity**: Verify all stock >= 0
5. **Category Validity**: Validate against allowed categories
6. **Product Names**: Check for empty product names
7. **Date Format**: Validate date formats

**Output**: `reports/data_quality_report.csv`

**Report Format**:

```
check,column,status,details,count
Missing Values,product_id,PASS,No missing values,0
Missing Values,product_name,PASS,No missing values,0
...
```

**Status Values**:

- `PASS`: Check successful, no issues found
- `FAIL`: Check failed, issues detected

### Step 3: Database Upload (`upload_to_db.py`)

**Purpose**: Store cleaned data in relational database

**Process**:

1. **Connect to Database**: Establish connection (SQLite/MySQL/PostgreSQL)
2. **Create Schema**: Create products table with proper data types and indexes
3. **Upload Data**: Insert cleaned CSV data into database
4. **Verify Upload**: Confirm successful insertion
5. **Generate Statistics**: Calculate data statistics

**Table Structure**:

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

**Database Support**:

- SQLite (default, file-based)
- MySQL (networked)
- PostgreSQL (networked)

### Step 4: Automation Orchestration (`automate_pipeline.py`)

**Purpose**: Single command to run entire pipeline

**Execution Flow**:

```
python automate_pipeline.py
├── Step 1: Clean Data
├── Step 2: Validate Data
├── Step 3: Upload to Database
└── Step 4: Generate Report
```

**Output Files**:

- `data/cleaned_products.csv`
- `reports/data_quality_report.csv`
- `reports/pipeline_execution_report.txt`
- `ecommerce.db` (SQLite database)

### Step 5: REST API (`api/app.py`)

**Purpose**: Provide REST endpoints for data access

**Available Endpoints**:

1. **GET /products**
   - Get all products with pagination
   - Query Parameters: skip, limit, category
   - Returns: List of products

2. **GET /products/{product_id}**
   - Get specific product by ID
   - Returns: Single product object

3. **GET /products/category/{category}**
   - Get products by category
   - Returns: List of products in category

4. **GET /stats**
   - Get database statistics
   - Returns: Product count, price range, stock info

5. **POST /upload**
   - Upload CSV file to database
   - Parameters: file_path
   - Returns: Upload status

6. **GET /health**
   - Health check endpoint
   - Returns: Database connection status

## Data Quality Standards

### Before Pipeline

- Missing values: 3-5%
- Invalid data: 10-15%
- Duplicates: 5%
- Data size: ~1500 rows

### After Pipeline

- Missing values: 0%
- Invalid data: 0%
- Duplicates: 0%
- Data size: ~1200 rows (after cleaning)
- Data quality score: 100%

## Performance Metrics

- **Data Cleaning**: <1 second
- **Validation**: <0.5 seconds
- **Database Upload**: <2 seconds
- **Total Pipeline**: <5 seconds
- **Data Throughput**: ~300 rows/second

## Usage Examples

### Run Full Pipeline

```bash
python scripts/automate_pipeline.py
```

### Run Individual Steps

```bash
# Clean only
python scripts/clean_data.py

# Validate only
python scripts/validate_data.py

# Upload only
python scripts/upload_to_db.py
```

### Use MySQL Database

```bash
python scripts/automate_pipeline.py --db-type mysql
```

### Start API Server

```bash
cd api
uvicorn app:app --reload
```

### Query API

```bash
curl http://localhost:8000/products?limit=10
curl http://localhost:8000/products/PROD_00001
curl http://localhost:8000/stats
```

## Error Handling

Pipeline includes comprehensive error handling:

- Invalid data type conversions
- Missing or corrupted files
- Database connection failures
- Schema validation errors

All errors are logged with descriptive messages in `pipeline.log`.

## Monitoring and Logging

- All operations logged to console and log file
- Each step generates detailed output
- Validation report shows all quality issues
- Execution report documents pipeline run

## Future Enhancements

1. **Incremental Updates**: Process only new/updated data
2. **Data Profiling**: Generate advanced data statistics
3. **Email Notifications**: Alert on pipeline completion
4. **Scheduling**: Automate pipeline runs (Airflow/Celery)
5. **Data Versioning**: Track data changes over time
6. **Advanced Monitoring**: Real-time dashboards

---

**Version**: 1.0
**Last Updated**: 2024
**Maintained By**: Data Engineering Team
