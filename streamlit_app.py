"""
Streamlit dashboard for the e-commerce data pipeline.

Reads the same database as the pipeline/API ($DATABASE_URL or the project-root
ecommerce.db) plus the latest pipeline reports.

Run:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect, select

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from config import EXECUTION_REPORT, REJECTED_DATA, get_db_url  # noqa: E402
from upload_to_db import products  # noqa: E402

SERIES_COLOR = "#2a78d6"  # single-series charts: one hue, no legend needed
LOW_STOCK = 10

st.set_page_config(page_title="E-commerce Pipeline Dashboard", layout="wide")


@st.cache_data(ttl=60)
def load_products(db_url: str) -> pd.DataFrame | None:
    """Return all products, or None if the table doesn't exist yet."""
    engine = create_engine(db_url)
    try:
        if "products" not in inspect(engine).get_table_names():
            return None
        with engine.connect() as conn:
            return pd.read_sql(select(products), conn)
    finally:
        engine.dispose()


@st.cache_data(ttl=60)
def load_run_report(path: str) -> dict | None:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_data(ttl=60)
def load_rejected(path: str) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_csv(p, dtype=str) if p.exists() else None


st.title("E-commerce Data Pipeline")

df = load_products(get_db_url())
if df is None or df.empty:
    st.warning(
        "No product data yet. Run `python generate_raw_data.py` and "
        "`python scripts/automate_pipeline.py`, then refresh."
    )
    st.stop()

# --- last pipeline run -----------------------------------------------------------------
report = load_run_report(str(EXECUTION_REPORT.with_suffix(".json")))
if report:
    ok = report["status"] == "SUCCESS"
    v = report.get("validation", {})
    msg = (
        f"Last run **{report['status']}** at {report['started_at']} · "
        f"{v.get('passed', 0)} checks passed, {v.get('failed', 0)} failed · "
        f"{report.get('rows_upserted', 0):,} rows upserted"
    )
    (st.success if ok else st.error)(msg, icon="✅" if ok else "❌")
    if report.get("error"):
        st.caption(f"Error: {report['error']}")

# --- filters (one row, above the charts) -----------------------------------------------
all_categories = sorted(df["category"].unique())
price_min, price_max = float(df["price"].min()), float(df["price"].max())
f1, f2 = st.columns([2, 1])
selected = f1.multiselect("Categories", all_categories, default=all_categories)
if price_min < price_max:
    price_range = f2.slider("Price range ($)", price_min, price_max, (price_min, price_max))
else:  # st.slider rejects min == max
    price_range = (price_min, price_max)
    f2.caption(f"All products cost ${price_min:,.2f}")

view = df[df["category"].isin(selected) & df["price"].between(*price_range)]
if view.empty:
    st.info("No products match the current filters.")
    st.stop()

# --- KPI row ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Products", f"{len(view):,}")
k2.metric("Categories", view["category"].nunique())
k3.metric("Avg price", f"${view['price'].mean():,.2f}")
k4.metric("Total stock", f"{int(view['stock'].sum()):,}")
k5.metric(f"Low stock (<{LOW_STOCK})", int((view["stock"] < LOW_STOCK).sum()))

# --- charts: one measure per chart, sorted, single hue ---------------------------------
by_cat = (
    view.groupby("category")
    .agg(products=("product_id", "count"), avg_price=("price", "mean"))
    .sort_values("products", ascending=False)
)
c1, c2 = st.columns(2)
with c1:
    st.subheader("Products per category")
    st.bar_chart(by_cat["products"], horizontal=True, color=SERIES_COLOR,
                 x_label="Products", y_label="")
with c2:
    st.subheader("Average price per category ($)")
    st.bar_chart(by_cat["avg_price"].round(2).sort_values(ascending=False), horizontal=True,
                 color=SERIES_COLOR, x_label="Avg price ($)", y_label="")

rejected = load_rejected(str(REJECTED_DATA))
c3, c4 = st.columns(2)
with c3:
    st.subheader("Rejected rows by reason (last run)")
    if rejected is None or rejected.empty:
        st.caption("No rejected rows recorded.")
    else:
        reasons = rejected["rejection_reason"].value_counts()
        st.bar_chart(reasons, horizontal=True, color=SERIES_COLOR, x_label="Rows", y_label="")
with c4:
    st.subheader(f"Low stock (<{LOW_STOCK})")
    low = view[view["stock"] < LOW_STOCK].sort_values("stock")
    st.dataframe(low[["product_id", "product_name", "category", "stock", "supplier"]],
                 hide_index=True, width="stretch")

# --- table view ------------------------------------------------------------------------
st.subheader("Products")
st.dataframe(
    view.drop(columns=["created_at", "updated_at"]).sort_values("product_id"),
    hide_index=True,
    width="stretch",
    column_config={"price": st.column_config.NumberColumn(format="$%.2f")},
)
st.download_button("Download filtered CSV", view.to_csv(index=False), "products_filtered.csv")
