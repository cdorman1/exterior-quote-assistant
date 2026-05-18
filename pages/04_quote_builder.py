import streamlit as st

from src.auth import require_auth
from src.constants import TRADES
from src.database import SessionLocal, init_db
from src.models import LaborTask, Material, MaterialPrice, Project, Quote, QuoteLineItem
from src.pricing_engine import (
    calculate_labor_cost,
    calculate_material_cost,
    calculate_quote_totals,
    calculate_vinyl_siding_takeoff,
    RectangularOpening,
    RectangularWall,
    TriangularGable,
)

require_auth()
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
    use_siding_takeoff = trade == "siding"

    materials = db.query(Material).filter(Material.trade == trade, Material.active.is_(True)).order_by(Material.name).all()
    labor_tasks = db.query(LaborTask).filter(LaborTask.trade == trade, LaborTask.active.is_(True)).order_by(LaborTask.name).all()

    if not materials or not labor_tasks:
        st.warning("Seed or add materials and labor tasks for this trade.")
        st.stop()

    if use_siding_takeoff:
        siding_materials = [m for m in materials if m.unit == "square"]
        siding_labor_tasks = [t for t in labor_tasks if t.unit == "square"]
        if siding_materials:
            materials = siding_materials
        if siding_labor_tasks:
            labor_tasks = siding_labor_tasks

    material_options = {m.name: m for m in materials}
    labor_options = {t.name: t for t in labor_tasks}

    with st.form("quote_builder"):
        st.subheader("Measurement and scope")
        quote_name = st.text_input("Quote name", value=f"{selected_project.project_name} Quote")
        if trade == "siding":
            use_siding_takeoff = st.checkbox("Use siding takeoff", value=True)

        siding_takeoff = None
        if use_siding_takeoff:
            st.caption("Siding takeoff mode uses wall, gable, and opening inputs to calculate square feet and siding squares.")
            waste_factor = st.number_input("Waste factor", min_value=0.0, value=0.10, step=0.01)

            wall_count = int(st.number_input("Wall count", min_value=0, max_value=20, value=4, step=1))
            walls: list[RectangularWall] = []
            for index in range(wall_count):
                st.markdown(f"**Wall {index + 1}**")
                wall_cols = st.columns(2)
                length_ft = wall_cols[0].number_input(
                    f"Wall {index + 1} length (ft)",
                    min_value=0.0,
                    value=30.0,
                    step=0.5,
                    key=f"siding_wall_length_{index}",
                )
                height_ft = wall_cols[1].number_input(
                    f"Wall {index + 1} height (ft)",
                    min_value=0.0,
                    value=10.0,
                    step=0.5,
                    key=f"siding_wall_height_{index}",
                )
                walls.append(RectangularWall(length_ft=length_ft, height_ft=height_ft))

            gable_count = int(st.number_input("Gable count", min_value=0, max_value=20, value=1, step=1))
            gables: list[TriangularGable] = []
            for index in range(gable_count):
                st.markdown(f"**Gable {index + 1}**")
                gable_cols = st.columns(2)
                base_ft = gable_cols[0].number_input(
                    f"Gable {index + 1} base (ft)",
                    min_value=0.0,
                    value=20.0,
                    step=0.5,
                    key=f"siding_gable_base_{index}",
                )
                height_ft = gable_cols[1].number_input(
                    f"Gable {index + 1} height (ft)",
                    min_value=0.0,
                    value=5.0,
                    step=0.5,
                    key=f"siding_gable_height_{index}",
                )
                gables.append(TriangularGable(base_ft=base_ft, height_ft=height_ft))

            opening_count = int(st.number_input("Opening count", min_value=0, max_value=20, value=2, step=1))
            openings: list[RectangularOpening] = []
            for index in range(opening_count):
                st.markdown(f"**Opening {index + 1}**")
                opening_cols = st.columns(2)
                width_ft = opening_cols[0].number_input(
                    f"Opening {index + 1} width (ft)",
                    min_value=0.0,
                    value=3.0,
                    step=0.5,
                    key=f"siding_opening_width_{index}",
                )
                height_ft = opening_cols[1].number_input(
                    f"Opening {index + 1} height (ft)",
                    min_value=0.0,
                    value=7.0,
                    step=0.5,
                    key=f"siding_opening_height_{index}",
                )
                openings.append(RectangularOpening(width_ft=width_ft, height_ft=height_ft))

            siding_takeoff = calculate_vinyl_siding_takeoff(
                walls=walls,
                gables=gables,
                openings=openings,
                waste_percent=waste_factor,
            )
            measured_quantity = float(siding_takeoff.siding_squares)
        else:
            measured_quantity = st.number_input("Measured quantity", min_value=0.0, value=10.0, step=1.0)
            waste_factor = st.number_input(
                "Waste factor",
                min_value=0.0,
                value=float(materials[0].default_waste_factor),
                step=0.01,
            )

        material = material_options[st.selectbox("Material", list(material_options))]
        labor_task = labor_options[st.selectbox("Labor task", list(labor_options))]

        latest_price = (
            db.query(MaterialPrice)
            .filter(MaterialPrice.material_id == material.id)
            .order_by(MaterialPrice.effective_date.desc())
            .first()
        )
        material_unit_cost = latest_price.unit_cost if latest_price else 0.0
        complexity_multiplier = st.number_input("Complexity multiplier", min_value=0.0, value=1.0, step=0.05)

        st.subheader("Other costs and pricing")
        permit_cost = st.number_input("Permit cost", min_value=0.0, value=0.0, step=50.0)
        disposal_cost = st.number_input("Disposal cost", min_value=0.0, value=0.0, step=50.0)
        equipment_cost = st.number_input("Equipment cost", min_value=0.0, value=0.0, step=50.0)
        overhead_cost = st.number_input("Overhead cost", min_value=0.0, value=0.0, step=50.0)
        target_margin = st.number_input("Target margin", min_value=0.0, max_value=0.95, value=0.40, step=0.01)
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=0.20, value=0.0, step=0.01)
        save_quote = st.form_submit_button("Calculate and save quote")

    if siding_takeoff is not None:
        takeoff_cols = st.columns(4)
        takeoff_cols[0].metric("Gross sq ft", f"{siding_takeoff.gross_square_feet:,.2f}")
        takeoff_cols[1].metric("Net sq ft", f"{siding_takeoff.net_square_feet:,.2f}")
        takeoff_cols[2].metric("Waste sq ft", f"{siding_takeoff.waste_square_feet:,.2f}")
        takeoff_cols[3].metric("Siding squares", f"{siding_takeoff.siding_squares:d}")

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
