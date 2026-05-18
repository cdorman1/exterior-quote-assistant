import pandas as pd
import streamlit as st

from src.database import SessionLocal, init_db
from src.models import ComplexityRule, LaborTask, WasteRule

st.title("Labor Rules")
init_db()
db = SessionLocal()
try:
    st.subheader("Labor tasks")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": t.id,
                    "Name": t.name,
                    "Trade": t.trade,
                    "Unit": t.unit,
                    "Base Labor Cost": t.base_labor_cost,
                    "Minimum Charge": t.minimum_charge,
                    "Active": t.active,
                }
                for t in db.query(LaborTask).order_by(LaborTask.trade, LaborTask.name).all()
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Waste rules")
    st.dataframe(pd.DataFrame([r.__dict__ for r in db.query(WasteRule).all()]).drop(columns=["_sa_instance_state"], errors="ignore"), use_container_width=True, hide_index=True)

    st.subheader("Complexity rules")
    st.dataframe(pd.DataFrame([r.__dict__ for r in db.query(ComplexityRule).all()]).drop(columns=["_sa_instance_state"], errors="ignore"), use_container_width=True, hide_index=True)
finally:
    db.close()
