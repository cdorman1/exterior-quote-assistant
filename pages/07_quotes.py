import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import ChangeOrderRate, Quote
from src.proposal_generator import generate_proposal_text

require_auth()
st.title("Quotes")
init_db()
db = SessionLocal()
try:
    quotes = db.query(Quote).order_by(Quote.created_at.desc()).all()
    st.subheader("Saved quotes")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": q.id,
                    "Quote": q.quote_name,
                    "Project": q.project.project_name,
                    "Customer": q.project.customer.name,
                    "Status": q.status,
                    "Total Cost": q.total_cost,
                    "Customer Price": q.customer_price,
                    "Created": q.created_at,
                }
                for q in quotes
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if quotes:
        quote_options = {f"{q.quote_name} ({q.id})": q for q in quotes}
        quote = quote_options[st.selectbox("Generate proposal text for quote", list(quote_options))]
        change_order_rates = db.query(ChangeOrderRate).all()
        proposal = generate_proposal_text(
            quote.project.customer,
            quote.project,
            quote,
            quote.line_items,
            change_order_rates,
        )
        st.subheader("Generated proposal text")
        st.text_area("Proposal", value=proposal, height=650)
    else:
        st.info("No saved quotes yet.")
finally:
    db.close()
