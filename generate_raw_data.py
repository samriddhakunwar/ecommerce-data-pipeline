"""
Generate a raw, messy e-commerce product dataset (fully reproducible).

Intentional data quality issues:
- invalid / missing prices, missing / negative stock, invalid dates
- exact duplicate rows and same-ID rows with different values
- missing and whitespace-padded product names, inconsistent categories
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw_products.csv"

SEED = 42
REFERENCE_DATE = date(2025, 12, 31)  # fixed, so output never depends on "today"
NUM_ROWS = 1500

PRODUCT_NAMES = [
    "Laptop Pro", "Wireless Mouse", "USB-C Cable", "Monitor 27inch", "Keyboard Mechanical",
    "Headphones Pro", "Web Camera", "Desk Lamp", "Phone Stand", "USB Hub",
    "SSD 1TB", "RAM 16GB", "Graphics Card", "Power Supply", "CPU Cooler",
    "Motherboard", "HDMI Cable", "Network Cable", "Surge Protector", "Cable Management",
    "Pen Tablet", "Microphone", "Speaker System", "Monitor Stand", "Laptop Bag",
]
CATEGORIES = [
    "Electronics", "Accessories", "STORAGE", "Peripherals", "Networking",
    "Audio", "Computing", "accessories", "ELECTRONICS", "storage", " Audio ", "Gadgets",
]
SUPPLIERS = [
    "TechSupply Co", "Global Electronics", "Digital Solutions", "Hardware World",
    "Tech Hub", "Component Store", "Supply Chain Inc", "Wholesale Tech", "Distributor Plus",
]


def generate(num_rows: int = NUM_ROWS, seed: int = SEED) -> pd.DataFrame:
    """Build the messy dataset. Same arguments -> identical output."""
    rng = random.Random(seed)
    rows = []
    for i in range(1, num_rows + 1):
        if rng.random() < 0.10:
            price = rng.choice([None, "N/A", "Invalid", -50, ""])
        else:
            price = round(rng.uniform(10, 2000), 2)

        if rng.random() < 0.05:
            stock = None
        elif rng.random() < 0.05:
            stock = rng.randint(-100, -1)
        else:
            stock = rng.randint(0, 1000)

        offset = rng.randint(0, 365)
        if rng.random() < 0.02:
            last_updated = "2025-13-45"  # invalid date
        else:
            last_updated = (REFERENCE_DATE - timedelta(days=offset)).isoformat()

        rows.append({
            "product_id": f"PROD_{i:05d}",
            "product_name": rng.choice(PRODUCT_NAMES),
            "category": rng.choice(CATEGORIES),
            "price": price,
            "stock": stock,
            "supplier": rng.choice(SUPPLIERS),
            "last_updated": last_updated,
        })
    df = pd.DataFrame(rows)

    # Exact duplicate rows (5%)
    df = pd.concat([df, df.sample(frac=0.05, random_state=seed)], ignore_index=True)

    # Same product_id, different values, newer date (1%): cleaning keeps the newest
    updates = df.sample(frac=0.01, random_state=seed + 1).copy()
    updates["price"] = [round(rng.uniform(10, 2000), 2) for _ in range(len(updates))]
    updates["last_updated"] = (REFERENCE_DATE + timedelta(days=1)).isoformat()
    df = pd.concat([df, updates], ignore_index=True)

    # Missing product names (3%) and whitespace-padded names (2%)
    idx = rng.sample(range(len(df)), int(len(df) * 0.05))
    cut = int(len(df) * 0.03)
    df.loc[idx[:cut], "product_name"] = None
    df.loc[idx[cut:], "product_name"] = "  " + df.loc[idx[cut:], "product_name"] + "  "

    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main(output: Path = OUTPUT_FILE) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(output, index=False)
    print(f"Generated raw dataset with {len(df)} rows -> {output}")
    print("Intentional issues: invalid prices (~10%), missing/negative stock (~10%),")
    print("invalid dates (~2%), duplicates (~5% exact + ~1% same-ID updates),")
    print("missing names (~3%), padded names (~2%), inconsistent categories.")


if __name__ == "__main__":
    main()
