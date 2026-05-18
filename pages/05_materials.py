import pandas as pd
import streamlit as st

from src.database import SessionLocal, init_db
from src.models import Material, MaterialPrice

st.title("Materials")
init_db()
db = SessionLocal()
try:
    materials = db.query(Material).order_by(Material.trade, Material.name).all()
    prices = db.query(MaterialPrice).join(Material).order_by(Material.trade, Material.name).all()

    st.subheader("Materials")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": m.id,
                    "Name": m.name,
                    "Trade": m.trade,
                    "Category": m.category,
                    "Unit": m.unit,
                    "Default Waste": m.default_waste_factor,
                    "Active": m.active,
                }
                for m in materials
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Material prices")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Material": p.material.name,
                    "Supplier": p.supplier,
                    "Unit Cost": p.unit_cost,
                    "Effective": p.effective_date,
                    "Expiration": p.expiration_date,
                    "Notes": p.notes,
                }
                for p in prices
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
