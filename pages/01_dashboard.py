from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
from sqlalchemy import func

from src.auth import require_auth
from src.branding import BRAND_NAME, LOGO_PATH, brand_css, render_brand_header
from src.database import SessionLocal, init_db
from src.models import Customer, Project, Quote


st.set_page_config(page_title=BRAND_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🏗️", layout="wide")
require_auth()
init_db()

st.markdown(brand_css(), unsafe_allow_html=True)
render_brand_header()

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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", customers, "Active records")
    c2.metric("Projects", projects, "Jobs in the pipeline")
    c3.metric("Quotes", quotes, f"{open_quotes} draft quotes")
    c4.metric("Total quoted value", f"${total_value:,.0f}", f"Avg quote ${avg_quote:,.0f}")

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown('<div class="brand-section">', unsafe_allow_html=True)
        st.markdown('<div class="brand-section-title">Recent quotes</div>', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="brand-section">', unsafe_allow_html=True)
        st.markdown('<div class="brand-section-title">Quote status mix</div>', unsafe_allow_html=True)
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

        st.markdown('<div class="brand-section-title" style="margin-top:1rem;">Workflow</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="brand-step"><div class="brand-step-num">1</div><div class="brand-step-text">Add a customer.</div></div>
            <div class="brand-step"><div class="brand-step-num">2</div><div class="brand-step-text">Create a project.</div></div>
            <div class="brand-step"><div class="brand-step-num">3</div><div class="brand-step-text">Build the quote.</div></div>
            <div class="brand-step"><div class="brand-step-num">4</div><div class="brand-step-text">Review the proposal.</div></div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
finally:
    db.close()
