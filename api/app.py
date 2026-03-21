"""
FastAPI Application for E-commerce Data Pipeline
REST API for accessing product data
Run: uvicorn api.app:app --reload
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sqlalchemy import create_engine, text
from typing import List, Optional
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="E-commerce Data Pipeline API",
    description="API for accessing product data from pipeline",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
engine = create_engine('sqlite:///ecommerce.db')


# Pydantic models
class ProductBase(BaseModel):
    product_id: str
    product_name: str
    category: str
    price: float
    stock: int
    supplier: Optional[str] = None
    last_updated: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    class Config:
        from_attributes = True


class ProductStats(BaseModel):
    total_products: int
    categories: int
    min_price: float
    max_price: float
    avg_price: float
    total_stock: int


# Routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-commerce Data Pipeline API",
        "version": "1.0.0",
        "endpoints": [
            "/products",
            "/products/{product_id}",
            "/products/category/{category}",
            "/stats",
            "/upload"
        ]
    }


@app.get("/products", response_model=List[Product])
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None
):
    """Get all products with pagination and optional category filter"""
    try:
        with engine.connect() as conn:
            if category:
                query = text(
                    "SELECT * FROM products WHERE category = :category LIMIT :limit OFFSET :skip"
                )
                result = conn.execute(query, {
                    "category": category,
                    "limit": limit,
                    "skip": skip
                })
            else:
                query = text("SELECT * FROM products LIMIT :limit OFFSET :skip")
                result = conn.execute(query, {"limit": limit, "skip": skip})

            columns = result.keys()
            products = [dict(zip(columns, row)) for row in result.fetchall()]
            return products

    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail="Error fetching products")


@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a specific product by ID"""
    try:
        with engine.connect() as conn:
            query = text("SELECT * FROM products WHERE product_id = :product_id")
            result = conn.execute(query, {"product_id": product_id})
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Product not found")

            columns = result.keys()
            product = dict(zip(columns, row))
            return product

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=500, detail="Error fetching product")


@app.get("/products/category/{category}", response_model=List[Product])
async def get_products_by_category(category: str):
    """Get all products in a specific category"""
    try:
        with engine.connect() as conn:
            query = text("SELECT * FROM products WHERE category = :category")
            result = conn.execute(query, {"category": category})

            columns = result.keys()
            products = [dict(zip(columns, row)) for row in result.fetchall()]

            if not products:
                raise HTTPException(status_code=404, detail="No products found in this category")

            return products

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching products by category: {e}")
        raise HTTPException(status_code=500, detail="Error fetching products")


@app.get("/stats", response_model=ProductStats)
async def get_statistics():
    """Get statistics about products"""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    COUNT(*) as total_products,
                    COUNT(DISTINCT category) as categories,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price) as avg_price,
                    SUM(stock) as total_stock
                FROM products
            """)
            result = conn.execute(query)
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="No data available")

            stats = {
                "total_products": row[0],
                "categories": row[1],
                "min_price": float(row[2]),
                "max_price": float(row[3]),
                "avg_price": float(row[4]),
                "total_stock": int(row[5])
            }
            return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")


@app.post("/upload")
async def upload_file(file_path: str = Query(...)):
    """Upload data from CSV file"""
    try:
        df = pd.read_csv(file_path)
        df.to_sql('products', engine, if_exists='append', index=False)
        return {
            "status": "success",
            "message": f"Successfully uploaded {len(df)} products",
            "rows_uploaded": len(df)
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=400, detail=f"Error uploading file: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result:
                return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
