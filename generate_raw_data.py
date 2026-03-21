"""
Generate raw messy e-commerce product dataset
Contains intentional data quality issues:
- Missing values
- Invalid prices
- Duplicate rows
- Inconsistent categories
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# Generate raw messy data
num_rows = 1500

product_names = [
    'Laptop Pro', 'Wireless Mouse', 'USB-C Cable', 'Monitor 27inch', 'Keyboard Mechanical',
    'Headphones Pro', 'Web Camera', 'Desk Lamp', 'Phone Stand', 'USB Hub',
    'SSD 1TB', 'RAM 16GB', 'Graphics Card', 'Power Supply', 'CPU Cooler',
    'Motherboard', 'HDMI Cable', 'Network Cable', 'Surge Protector', 'Cable Management',
    'Pen Tablet', 'Microphone', 'Speaker System', 'Monitor Stand', 'Laptop Bag'
]

categories = [
    'Electronics', 'Accessories', 'STORAGE', 'Peripherals', 'Networking',
    'Audio', 'Computing', 'accessories', 'ELECTRONICS', 'storage'
]

suppliers = [
    'TechSupply Co', 'Global Electronics', 'Digital Solutions', 'Hardware World',
    'Tech Hub', 'Component Store', 'Supply Chain Inc', 'Wholesale Tech', 'Distributor Plus'
]

# Create base data
data = {
    'product_id': [f'PROD_{i:05d}' for i in range(1, num_rows + 1)],
    'product_name': [random.choice(product_names) for _ in range(num_rows)],
    'category': [random.choice(categories) for _ in range(num_rows)],
    'price': [],
    'stock': [],
    'supplier': [random.choice(suppliers) for _ in range(num_rows)],
    'last_updated': []
}

# Add intentional data quality issues
for i in range(num_rows):
    # Invalid prices (10% of rows)
    if random.random() < 0.10:
        data['price'].append(random.choice([None, 'N/A', 'Invalid', -50, '']))
    else:
        data['price'].append(round(random.uniform(10, 2000), 2))

    # Invalid stock (5% missing, 5% negative)
    if random.random() < 0.05:
        data['stock'].append(None)
    elif random.random() < 0.05:
        data['stock'].append(random.randint(-100, -1))
    else:
        data['stock'].append(random.randint(0, 1000))

    # Dates with some invalid ones
    days_offset = random.randint(0, 365)
    if random.random() < 0.02:
        data['last_updated'].append('2025-13-45')  # Invalid date
    else:
        data['last_updated'].append((datetime.now() - timedelta(days=days_offset)).strftime('%Y-%m-%d'))

df = pd.DataFrame(data)

# Add some duplicates (5%)
duplicates = df.sample(int(len(df) * 0.05))
df = pd.concat([df, duplicates], ignore_index=True)

# Add some rows with missing product names
missing_indices = random.sample(range(len(df)), int(len(df) * 0.03))
for idx in missing_indices:
    df.loc[idx, 'product_name'] = None

# Shuffle dataframe
df = df.sample(frac=1).reset_index(drop=True)

# Save raw data
df.to_csv('data/raw_products.csv', index=False)
print(f"Generated raw dataset with {len(df)} rows")
print(f"Data quality issues intentionally added:")
print(f"- Invalid prices: ~10%")
print(f"- Missing values: ~3-5%")
print(f"- Negative stock: ~5%")
print(f"- Duplicate rows: ~5%")
print(f"- Inconsistent categories: Various")
print(f"\nDataset saved to: data/raw_products.csv")
