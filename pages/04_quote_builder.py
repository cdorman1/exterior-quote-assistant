import streamlit as st

from src.constants import TRADES
from src.database import SessionLocal, init_db
from src.models import LaborTask, Material, MaterialPrice, Project, Quote, QuoteLineItem
from src.pricing_engine import (
    calculate_labor_cost,
    calculate_material_cost,
    calculate_quote_totals,
)

st.title("Quote Builder")
init_db()
db = SessionLocal()
try:
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    if not projects:
        st.warning("Create a project before building a quote.")
        st.stop()

    project_options = {f"{p.project_name} - {p.customer.name} ({p.id})": p for p in projects}
    selected_project = project_options[st.selectbox("Project", list(project_options))]
    allowed_trades = TRADES if selected_project.trade_scope == "combination" else [selected_project.trade_scope]
    trade = st.selectbox("Trade", allowed_trades)

    materials = db.query(Material).filter(Material.trade == trade, Material.active.is_(True)).order_by(Material.name).all()
    labor_tasks = db.query(LaborTask).filter(LaborTask.trade == trade, LaborTask.active.is_(True)).order_by(LaborTask.name).all()

    if not materials or not labor_tasks:
        st.warning("Seed or add materials and labor tasks for this trade.")
        st.stop()

    material_options = {m.name: m for m in materials}
    labor_options = {t.name: t for t in labor_tasks}

    with st.form("quote_builder"):
        st.subheader("Measurement and scope")
        quote_name = st.text_input("Quote name", value=f"{selected_project.project_name} Quote")
        measured_quantity = st.number_input("Measured quantity", min_value=0.0, value=10.0, step=1.0)
        material = material_options[st.selectbox("Material", list(material_options))]
        labor_task = labor_options[st.selectbox("Labor task", list(labor_options))]

        latest_price = (
            db.query(MaterialPrice)
            .filter(MaterialPrice.material_id == material.id)
            .order_by(MaterialPrice.effective_date.desc())
            .first()
        )
        material_unit_cost = latest_price.unit_cost if latest_price else 0.0
        waste_factor = st.number_input("Waste factor", min_value=0.0, value=float(material.default_waste_factor), step=0.01)
        complexity_multiplier = st.number_input("Complexity multiplier", min_value=0.0, value=1.0, step=0.05)

        st.subheader("Other costs and pricing")
        permit_cost = st.number_input("Permit cost", min_value=0.0, value=0.0, step=50.0)
        disposal_cost = st.number_input("Disposal cost", min_value=0.0, value=0.0, step=50.0)
        equipment_cost = st.number_input("Equipment cost", min_value=0.0, value=0.0, step=50.0)
        overhead_cost = st.number_input("Overhead cost", min_value=0.0, value=0.0, step=50.0)
        target_margin = st.number_input("Target margin", min_value=0.0, max_value=0.95, value=0.40, step=0.01)
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=0.20, value=0.0, step=0.01)
        save_quote = st.form_submit_button("Calculate and save quote")

    material_cost = calculate_material_cost(measured_quantity, material_unit_cost, waste_factor)
    labor_cost = calculate_labor_cost(
        measured_quantity,
        labor_task.base_labor_cost,
        complexity_multiplier,
        labor_task.minimum_charge,
    )
    draft_line_items = [
        {
            "trade": trade,
            "item_type": "material",
            "description": material.name,
            "quantity": measured_quantity,
            "unit": material.unit,
            "unit_cost": material_unit_cost,
            "waste_factor": waste_factor,
            "complexity_multiplier": 1.0,
            "line_cost": material_cost,
        },
        {
            "trade": trade,
            "item_type": "labor",
            "description": labor_task.name,
            "quantity": measured_quantity,
            "unit": labor_task.unit,
            "unit_cost": labor_task.base_labor_cost,
            "waste_factor": 0.0,
            "complexity_multiplier": complexity_multiplier,
            "line_cost": labor_cost,
        },
    ]
    totals = calculate_quote_totals(
        draft_line_items,
        permit_cost,
        disposal_cost,
        equipment_cost,
        overhead_cost,
        target_margin,
        tax_rate,
    )

    cols = st.columns(4)
    cols[0].metric("Material cost", f"${totals['material_cost']:,.2f}")
    cols[1].metric("Labor cost", f"${totals['labor_cost']:,.2f}")
    cols[2].metric("Total cost", f"${totals['total_cost']:,.2f}")
    cols[3].metric("Customer price", f"${totals['customer_price']:,.2f}")

    if save_quote:
        quote = Quote(
            project_id=selected_project.id,
            quote_name=quote_name,
            status="draft",
            target_margin=target_margin,
            tax_rate=tax_rate,
            permit_cost=permit_cost,
            disposal_cost=disposal_cost,
            equipment_cost=equipment_cost,
            overhead_cost=overhead_cost,
            material_cost=totals["material_cost"],
            labor_cost=totals["labor_cost"],
            total_cost=totals["total_cost"],
            customer_price=totals["customer_price"],
        )
        db.add(quote)
        db.flush()
        for item in draft_line_items:
            db.add(QuoteLineItem(quote_id=quote.id, **item))
        db.commit()
        st.success(f"Quote {quote.id} saved.")
finally:
    db.close()
