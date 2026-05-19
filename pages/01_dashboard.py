from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
from sqlalchemy import func

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import Customer, Project, Quote


st.set_page_config(page_title="EK View Construction Quote Assistant", layout="wide")
require_auth()
init_db()

st.title("EK View Construction Quote Assistant")
st.caption("Contractor quoting dashboard for roofing and siding jobs.")

db = SessionLocal()
try:
    customers = db.query(func.count(Customer.id)).scalar() or 0
    projects = db.query(func.count(Project.id)).scalar() or 0
    quotes = db.query(func.count(Quote.id)).scalar() or 0
    total_value = db.query(func.coalesce(func.sum(Quote.customer_price), 0)).scalar() or 0
    avg_quote = (total_value / quotes) if quotes else 0
    open_quotes = db.query(func.count(Quote.id)).filter(Quote.status == "draft").scalar() or 0

    quote_rows = db.query(Quote).order_by(Quote.created_at.desc()).limit(8).all()
    status_counts = Counter(q.status for q in db.query(Quote).all())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Customers", customers, "Active records")
    col2.metric("Projects", projects, "Jobs in the pipeline")
    col3.metric("Quotes", quotes, f"{open_quotes} draft quotes")
    col4.metric("Total quoted value", f"${total_value:,.0f}", f"Avg quote ${avg_quote:,.0f}")

    left, right = st.columns([1.55, 1])
    with left:
        st.subheader("Recent quotes")
        recent_data = pd.DataFrame(
            [
                {
                    "Quote": q.quote_name,
                    "Project": q.project.project_name,
                    "Customer": q.project.customer.name,
                    "Status": q.status,
                    "Customer Price": q.customer_price,
                    "Created": q.created_at.strftime("%Y-%m-%d"),
                }
                for q in quote_rows
            ]
        )
        if recent_data.empty:
            st.info("No quotes yet.")
        else:
            st.dataframe(recent_data, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Quote status mix")
        if status_counts:
            status_data = pd.DataFrame(
                [
                    {"Status": status, "Count": count}
                    for status, count in sorted(status_counts.items(), key=lambda item: item[0])
                ]
            )
            st.bar_chart(status_data.set_index("Status"))
        else:
            st.info("No quotes yet.")

        st.subheader("Workflow")
        st.markdown(
            """
            1. Add a customer
            2. Create a project
            3. Build the quote
            4. Review the proposal
            """
        )
finally:
    db.close()
