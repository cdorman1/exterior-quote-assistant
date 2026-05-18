import pandas as pd
import streamlit as st

from src.constants import PROJECT_STATUSES, PROJECT_TYPES, TRADE_SCOPES
from src.database import SessionLocal, init_db
from src.models import Customer, Project

st.title("Projects")
init_db()
db = SessionLocal()
try:
    customers = db.query(Customer).order_by(Customer.name).all()
    if not customers:
        st.warning("Create a customer before adding projects.")
    else:
        customer_options = {f"{c.name} ({c.id})": c.id for c in customers}
        with st.form("project_form"):
            st.subheader("Create project")
            customer_id = customer_options[st.selectbox("Customer", list(customer_options))]
            project_name = st.text_input("Project name")
            project_type = st.selectbox("Project type", PROJECT_TYPES)
            trade_scope = st.selectbox("Trade scope", TRADE_SCOPES)
            status = st.selectbox("Status", PROJECT_STATUSES)
            address = st.text_area("Address")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Save project")
            if submitted and project_name:
                db.add(
                    Project(
                        customer_id=customer_id,
                        project_name=project_name,
                        project_type=project_type,
                        trade_scope=trade_scope,
                        status=status,
                        address=address,
                        notes=notes,
                    )
                )
                db.commit()
                st.success("Project saved.")
                st.rerun()

    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    st.subheader("All projects")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": p.id,
                    "Project": p.project_name,
                    "Customer": p.customer.name,
                    "Type": p.project_type,
                    "Trade": p.trade_scope,
                    "Status": p.status,
                    "Address": p.address,
                }
                for p in projects
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
