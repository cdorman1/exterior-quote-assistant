import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import ChangeOrderRate

require_auth()
st.title("Change Orders")
init_db()
db = SessionLocal()
try:
    rates = db.query(ChangeOrderRate).order_by(ChangeOrderRate.trade, ChangeOrderRate.description).all()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": r.id,
                    "Trade": r.trade,
                    "Description": r.description,
                    "Unit": r.unit,
                    "Unit Price": r.unit_price,
                    "Notes": r.notes,
                }
                for r in rates
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
