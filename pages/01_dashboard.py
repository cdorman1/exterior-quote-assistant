import pandas as pd
import streamlit as st
from sqlalchemy import func

from src.database import SessionLocal, init_db
from src.models import Customer, Project, Quote

st.title("Dashboard")
init_db()
db = SessionLocal()
try:
    customers = db.query(func.count(Customer.id)).scalar() or 0
    projects = db.query(func.count(Project.id)).scalar() or 0
    quotes = db.query(func.count(Quote.id)).scalar() or 0
    total_value = db.query(func.coalesce(func.sum(Quote.customer_price), 0)).scalar() or 0

    cols = st.columns(4)
    cols[0].metric("Customers", customers)
    cols[1].metric("Projects", projects)
    cols[2].metric("Quotes", quotes)
    cols[3].metric("Total quoted value", f"${total_value:,.2f}")

    rows = [
        {
            "Quote": q.quote_name,
            "Project": q.project.project_name,
            "Status": q.status,
            "Customer Price": q.customer_price,
            "Created": q.created_at,
        }
        for q in db.query(Quote).order_by(Quote.created_at.desc()).limit(10).all()
    ]
    st.subheader("Recent quotes")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
finally:
    db.close()
