from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
from sqlalchemy import func

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import Customer, Project, Quote


def _kpi_card(label: str, value: str, detail: str = "") -> str:
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-detail">{detail}</div>
    </div>
    """

st.set_page_config(page_title="EK View Construction Quote Assistant", layout="wide")
require_auth()
init_db()

st.markdown(
    """
    <style>
      .dashboard-hero {
        padding: 1.15rem 1.25rem;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.04), rgba(14, 116, 144, 0.08));
        margin-bottom: 1rem;
      }
      .dashboard-hero h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.1;
      }
      .dashboard-hero p {
        margin: 0.4rem 0 0;
        color: rgba(49, 51, 63, 0.8);
      }
      .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0 1.25rem;
      }
      .kpi-card {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        background: white;
      }
      .kpi-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(49, 51, 63, 0.65);
      }
      .kpi-value {
        font-size: 1.75rem;
        line-height: 1.1;
        font-weight: 700;
        margin-top: 0.35rem;
      }
      .kpi-detail {
        font-size: 0.9rem;
        color: rgba(49, 51, 63, 0.7);
        margin-top: 0.3rem;
      }
      .section-title {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 0.6rem;
      }
      .status-pill {
        display: inline-block;
        padding: 0.22rem 0.55rem;
        border-radius: 999px;
        font-size: 0.75rem;
        background: rgba(14, 116, 144, 0.1);
        color: rgb(15, 118, 110);
      }
      @media (max-width: 900px) {
        .kpi-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
      @media (max-width: 640px) {
        .kpi-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

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

    st.markdown(
        """
        <div class="dashboard-hero">
          <h1>EK View Construction Quote Assistant</h1>
          <p>Contractor quoting dashboard for roofing and siding jobs.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="kpi-grid">
          {_kpi_card("Customers", str(customers), "Active customer records")}
          {_kpi_card("Projects", str(projects), "Jobs in the pipeline")}
          {_kpi_card("Quotes", str(quotes), f"{open_quotes} draft quotes")}
          {_kpi_card("Total quoted value", f"${total_value:,.0f}", f"Avg quote ${avg_quote:,.0f}")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown('<div class="section-title">Recent quotes</div>', unsafe_allow_html=True)
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
        st.dataframe(recent_data, use_container_width=True, hide_index=True)

    with right:
        st.markdown('<div class="section-title">Quote status mix</div>', unsafe_allow_html=True)
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

        st.markdown('<div class="section-title" style="margin-top:1rem;">Workflow</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <span class="status-pill">1</span> Add a customer<br/>
            <span class="status-pill">2</span> Create a project<br/>
            <span class="status-pill">3</span> Build the quote<br/>
            <span class="status-pill">4</span> Review the proposal
            """,
            unsafe_allow_html=True,
        )
finally:
    db.close()
