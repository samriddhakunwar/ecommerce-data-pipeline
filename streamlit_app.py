"""
Streamlit dashboard for the e-commerce data pipeline.

Reads the same database as the pipeline/API ($DATABASE_URL or the project-root
ecommerce.db) plus the latest pipeline reports.

Run:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, func, inspect, select

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from config import get_db_url  # noqa: E402
from upload_to_db import products  # noqa: E402

logger = logging.getLogger(__name__)

SERIES_COLOR = "#2a78d6"  # single-series charts: one hue, no legend needed
LOW_STOCK = 10

st.set_page_config(page_title="E-commerce Pipeline Dashboard", page_icon="📦", layout="wide")


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


def has_products(db_url: str) -> bool:
    engine = create_engine(db_url)
    try:
        if "products" not in inspect(engine).get_table_names():
            return False
        with engine.connect() as conn:
            return bool(conn.execute(select(func.count()).select_from(products)).scalar())
    finally:
        engine.dispose()


@st.cache_resource(show_spinner=False)
def ensure_data(db_url: str) -> str | None:
    """Build the dataset on a cold start (e.g. Streamlit Community Cloud, where the
    gitignored ecommerce.db doesn't exist). Runs at most once per server process.
    Returns an error message, or None on success."""
    if has_products(db_url):
        return None
    if os.environ.get("DASHBOARD_AUTOBUILD", "1") == "0":
        return "autobuild disabled"
    import generate_raw_data
    from automate_pipeline import DataPipeline

    try:
        generate_raw_data.main(output=config.RAW_DATA)
        pipeline = DataPipeline(
            raw_data=config.RAW_DATA,
            db_url=db_url,
            data_dir=config.DATA_DIR,
            reports_dir=config.REPORTS_DIR,
        )
        if not pipeline.run_pipeline():
            return pipeline.error or "pipeline failed"
    except Exception as exc:  # keep the UI up; details go to the log
        logger.exception("Dashboard data build failed")
        return str(exc)
    return None


st.title("📦 E-commerce Data Pipeline")
st.caption("Product catalog, inventory health and data quality from the latest pipeline run.")

DB_URL = get_db_url()
with st.spinner("Building the dataset (first start only)…"):
    build_error = ensure_data(DB_URL)
df = load_products(DB_URL)
if df is None or df.empty:
    load_products.clear()  # don't cache "no data" for the next visitor
    df = load_products(DB_URL)
if df is None or df.empty:
    st.warning(
        "No product data yet. Run `python generate_raw_data.py` and "
        "`python scripts/automate_pipeline.py`, then refresh."
    )
    if build_error and build_error != "autobuild disabled":
        st.caption("Automatic build failed; see the app logs for details.")
    st.stop()

# --- last pipeline run -----------------------------------------------------------------
report = load_run_report(str(config.EXECUTION_REPORT.with_suffix(".json")))
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

# --- filters (sidebar) -----------------------------------------------------------------
all_categories = sorted(df["category"].unique())
price_min, price_max = float(df["price"].min()), float(df["price"].max())
with st.sidebar:
    st.header("Filters")
    selected = st.multiselect("Categories", all_categories, default=all_categories)
    if price_min < price_max:
        price_range = st.slider("Price range ($)", price_min, price_max, (price_min, price_max))
    else:  # st.slider rejects min == max
        price_range = (price_min, price_max)
        st.caption(f"All products cost ${price_min:,.2f}")
    st.divider()
    if st.button("Refresh data", icon="🔄", width="stretch"):
        st.cache_data.clear()
        st.rerun()

view = df[df["category"].isin(selected) & df["price"].between(*price_range)]
if view.empty:
    st.info("No products match the current filters.")
    st.stop()

# --- KPI row ---------------------------------------------------------------------------
low = view[view["stock"] < LOW_STOCK].sort_values("stock")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Products", f"{len(view):,}", border=True)
k2.metric("Categories", view["category"].nunique(), border=True)
k3.metric("Avg price", f"${view['price'].mean():,.2f}", border=True)
k4.metric("Total stock", f"{int(view['stock'].sum()):,}", border=True)
k5.metric("Inventory value", f"${(view['price'] * view['stock']).sum():,.0f}", border=True)
k6.metric(f"Low stock (<{LOW_STOCK})", len(low), border=True)

overview, inventory, quality, catalog = st.tabs(
    ["📊 Overview", f"⚠️ Low stock ({len(low)})", "🧹 Data quality", "📋 Products"]
)

# --- charts: one measure per chart, sorted, single hue ---------------------------------
by_cat = (
    view.groupby("category")
    .agg(products=("product_id", "count"), avg_price=("price", "mean"))
    .sort_values("products", ascending=False)
)
with overview:
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("Products per category")
        st.bar_chart(by_cat["products"], horizontal=True, color=SERIES_COLOR,
                     x_label="Products", y_label="")
    with c2.container(border=True):
        st.subheader("Average price per category ($)")
        st.bar_chart(by_cat["avg_price"].round(2).sort_values(ascending=False),
                     horizontal=True, color=SERIES_COLOR, x_label="Avg price ($)", y_label="")

with inventory:
    if low.empty:
        st.success("No products below the low-stock threshold.", icon="✅")
    else:
        st.dataframe(low[["product_id", "product_name", "category", "stock", "supplier"]],
                     hide_index=True, width="stretch")

with quality:
    rejected = load_rejected(str(config.REJECTED_DATA))
    if rejected is None or rejected.empty:
        st.caption("No rejected rows recorded.")
    else:
        st.subheader("Rejected rows by reason (last run)")
        reasons = rejected["rejection_reason"].value_counts()
        st.bar_chart(reasons, horizontal=True, color=SERIES_COLOR, x_label="Rows", y_label="")
        with st.expander(f"Show {len(rejected):,} rejected rows"):
            st.dataframe(rejected, hide_index=True, width="stretch")

# --- table view ------------------------------------------------------------------------
with catalog:
    st.dataframe(
        view.drop(columns=["created_at", "updated_at"]).sort_values("product_id"),
        hide_index=True,
        width="stretch",
        column_config={"price": st.column_config.NumberColumn(format="$%.2f")},
    )
    st.download_button("Download filtered CSV", view.to_csv(index=False),
                       "products_filtered.csv", icon="⬇️")
