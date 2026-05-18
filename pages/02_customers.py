import pandas as pd
import streamlit as st

from src.database import SessionLocal, init_db
from src.models import Customer

st.title("Customers")
init_db()
db = SessionLocal()
try:
    with st.form("customer_form"):
        st.subheader("Create customer")
        name = st.text_input("Name")
        company_name = st.text_input("Company name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        address = st.text_area("Address")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save customer")
        if submitted and name:
            db.add(Customer(name=name, company_name=company_name, phone=phone, email=email, address=address, notes=notes))
            db.commit()
            st.success("Customer saved.")
            st.rerun()

    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    st.subheader("All customers")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": c.id,
                    "Name": c.name,
                    "Company": c.company_name,
                    "Phone": c.phone,
                    "Email": c.email,
                    "Address": c.address,
                    "Created": c.created_at,
                }
                for c in customers
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
