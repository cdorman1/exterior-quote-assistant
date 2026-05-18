from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.constants import (
    LABOR_CONDITION_MULTIPLIERS,
    LABOR_DIFFICULTY_MULTIPLIERS,
    LABOR_METHOD_LABELS,
    TRADES,
)
from src.database import SessionLocal, init_db
from src.models import (
    ComplexityRule,
    LaborTask,
    Material,
    MaterialPrice,
    Project,
    Quote,
    QuoteLaborLineItem,
    QuoteLineItem,
)
from src.pricing_engine import (
    RectangularOpening,
    RectangularWall,
    TriangularGable,
    calculate_final_complexity_multiplier,
    calculate_labor_cost,
    calculate_labor_summary,
    calculate_material_cost,
    calculate_quote_totals,
    calculate_crew_day_labor,
    calculate_hourly_labor,
    calculate_subcontractor_labor,
    calculate_vinyl_siding_takeoff,
)


def _project_summary(project: Project, trade: str, measured_quantity: float, unit: str, material_name: str, stories: float, complexity_label: str, access_label: str) -> list[tuple[str, str]]:
    return [
        ("Project name", project.project_name),
        ("Project type", project.project_type),
        ("Trade", trade),
        ("Measured quantity", f"{measured_quantity:,.2f}"),
        ("Unit", unit),
        ("Material type", material_name or "Not specified"),
        ("Stories", f"{stories:g}" if stories else "Not specified"),
        ("Complexity", complexity_label or "Not specified"),
        ("Access difficulty", access_label or "Not specified"),
    ]


def _selected_condition_multipliers(trade: str, selected_keys: list[str]) -> list[float]:
    condition_map = LABOR_CONDITION_MULTIPLIERS.get(trade, {})
    return [condition_map[key] for key in selected_keys if key in condition_map]


def _filtered_labor_tasks(db, trade: str, project_type: str) -> list[LaborTask]:
    tasks = (
        db.query(LaborTask)
        .filter(LaborTask.trade == trade, LaborTask.active.is_(True))
        .order_by(LaborTask.name)
        .all()
    )
    return [
        task
        for task in tasks
        if task.applies_to_project_type in {"both", project_type}
    ]


def _default_unit_based_rows(tasks: list[LaborTask], measured_quantity: float, final_multiplier: float) -> pd.DataFrame:
    rows = []
    for task in tasks:
        quantity = measured_quantity if task.unit not in {"job", "allowance"} else 1.0
        if quantity <= 0:
            quantity = 1.0
        complexity_multiplier = final_multiplier * (task.default_multiplier or 1.0)
        rows.append(
            {
                "include": True,
                "task_name": task.name,
                "quantity": quantity,
                "unit": task.unit,
                "base_rate": task.base_labor_cost,
                "minimum_charge": task.minimum_charge,
                "complexity_multiplier": complexity_multiplier,
                "calculated_cost": 0.0,
                "manual_override_cost": None,
                "override_reason": "",
                "final_cost": 0.0,
                "notes": task.notes or "",
            }
        )
    return pd.DataFrame(rows)


def _calculate_unit_based_labor(rows: pd.DataFrame, trade: str) -> list[dict]:
    labor_line_items: list[dict] = []
    for _, row in rows.iterrows():
        if not bool(row.get("include", False)):
            continue
        quantity = float(row.get("quantity", 0) or 0)
        base_rate = float(row.get("base_rate", 0) or 0)
        minimum_charge = float(row.get("minimum_charge", 0) or 0)
        complexity_multiplier = float(row.get("complexity_multiplier", 1) or 1)
        manual_override_cost = row.get("manual_override_cost")
        manual_override_cost = None if pd.isna(manual_override_cost) else float(manual_override_cost)
        override_reason = str(row.get("override_reason") or "").strip()
        result = calculate_labor_cost(
            quantity=quantity,
            labor_unit_cost=base_rate,
            complexity_multiplier=complexity_multiplier,
            minimum_charge=minimum_charge,
            manual_override_cost=manual_override_cost,
        )
        labor_line_items.append(
            {
                "trade": trade,
                "labor_method": "unit_based",
                "task_name": str(row.get("task_name", "")).strip(),
                "quantity": quantity,
                "unit": str(row.get("unit", "")).strip(),
                "base_rate": base_rate,
                "complexity_multiplier": complexity_multiplier,
                "minimum_charge": minimum_charge,
                "calculated_cost": result["calculated_cost"],
                "manual_override_cost": manual_override_cost,
                "final_cost": result["final_cost"],
                "override_reason": override_reason,
                "notes": str(row.get("notes") or "").strip(),
                "manual_override_applied": result["manual_override_applied"],
                "minimum_charge_applied": result["minimum_charge_applied"],
            }
        )
    return labor_line_items


def _labor_confidence(level_inputs: dict, labor_line_items: list[dict], trade: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    measured_quantity = float(level_inputs.get("measured_quantity", 0) or 0)
    if measured_quantity <= 0:
        reasons.append("Measured quantity is zero.")
    if not labor_line_items:
        reasons.append("No labor tasks were selected.")
    if any(item.get("base_rate", 0) == 0 for item in labor_line_items):
        reasons.append("At least one included task has a zero base rate.")
    if any(item.get("manual_override_applied") and not str(item.get("override_reason") or "").strip() for item in labor_line_items):
        reasons.append("A manual override is missing an override reason.")
    if any(key == "structural_repair_review_required" for key in level_inputs.get("selected_conditions", [])):
        reasons.append("Structural repair review is required.")
    if reasons:
        return "needs_review", reasons
    return "high_confidence", ["Labor estimate looks complete based on selected quantity, labor tasks, and difficulty."]


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

    materials = db.query(Material).filter(Material.trade == trade, Material.active.is_(True)).order_by(Material.name).all()
    labor_tasks = _filtered_labor_tasks(db, trade, selected_project.project_type)
    if not materials or not labor_tasks:
        st.warning("Seed or add materials and labor tasks for this trade.")
        st.stop()

    if trade == "siding":
        siding_materials = [m for m in materials if m.unit == "square"]
        if siding_materials:
            materials = siding_materials

    material_options = {m.name: m for m in materials}
    if "quote_draft" not in st.session_state:
        st.session_state.quote_draft = None

    with st.form("quote_builder"):
        st.subheader("Labor Estimate")
        quote_name = st.text_input("Quote name", value=f"{selected_project.project_name} Quote")

        summary_cols = st.columns(3)
        measured_quantity = summary_cols[0].number_input("Measured quantity", min_value=0.0, value=10.0, step=1.0)
        quantity_unit = summary_cols[1].selectbox(
            "Select quantity unit",
            ["square", "square_foot", "linear_foot", "each", "job", "allowance"],
        )
        stories = summary_cols[2].number_input("Stories", min_value=0.0, value=1.0, step=1.0)

        material = material_options[st.selectbox("Material", list(material_options))]
        latest_price = (
            db.query(MaterialPrice)
            .filter(MaterialPrice.material_id == material.id)
            .order_by(MaterialPrice.effective_date.desc())
            .first()
        )
        material_unit_cost = latest_price.unit_cost if latest_price else 0.0
        waste_factor = st.number_input("Waste factor", min_value=0.0, value=float(material.default_waste_factor), step=0.01)

        labor_method_label = st.selectbox("Select labor method", list(LABOR_METHOD_LABELS.values()))
        labor_method = next(code for code, label in LABOR_METHOD_LABELS.items() if label == labor_method_label)

        difficulty_label = st.selectbox("Select difficulty", list(LABOR_DIFFICULTY_MULTIPLIERS.keys()))
        base_difficulty_multiplier = LABOR_DIFFICULTY_MULTIPLIERS[difficulty_label]

        condition_options = LABOR_CONDITION_MULTIPLIERS.get(trade, {})
        selected_conditions = [
            condition_name
            for condition_name in condition_options
            if st.checkbox(condition_name.replace("_", " ").title(), key=f"condition_{trade}_{condition_name}")
        ]
        condition_multipliers = _selected_condition_multipliers(trade, selected_conditions)
        final_multiplier = calculate_final_complexity_multiplier(base_difficulty_multiplier, condition_multipliers)
        st.caption(f"Final complexity multiplier: {final_multiplier:.2f}")

        access_label = ", ".join(selected_conditions) if selected_conditions else "Not specified"
        st.markdown("**Project summary**")
        st.dataframe(
            pd.DataFrame(
                _project_summary(
                    selected_project,
                    trade,
                    measured_quantity,
                    quantity_unit,
                    material.name,
                    stories,
                    difficulty_label.replace("_", " ").title(),
                    access_label,
                ),
                columns=["Field", "Value"],
            ),
            use_container_width=True,
            hide_index=True,
        )

        unit_based_rows = pd.DataFrame()
        if labor_method == "unit_based":
            default_rows = _default_unit_based_rows(labor_tasks, measured_quantity, final_multiplier)
            if not default_rows.empty:
                unit_based_rows = st.data_editor(
                    default_rows,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="unit_based_labor_editor",
                    column_config={
                        "include": st.column_config.CheckboxColumn("Include"),
                        "task_name": st.column_config.TextColumn("Task name"),
                        "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=0.1),
                        "unit": st.column_config.TextColumn("Unit"),
                        "base_rate": st.column_config.NumberColumn("Base labor rate", min_value=0.0, step=1.0),
                        "minimum_charge": st.column_config.NumberColumn("Minimum charge", min_value=0.0, step=1.0),
                        "complexity_multiplier": st.column_config.NumberColumn("Complexity multiplier", min_value=0.0, step=0.01),
                        "calculated_cost": st.column_config.NumberColumn("Calculated cost", disabled=True),
                        "manual_override_cost": st.column_config.NumberColumn("Manual override cost", min_value=0.0, step=1.0),
                        "override_reason": st.column_config.TextColumn("Override reason"),
                        "final_cost": st.column_config.NumberColumn("Final cost", disabled=True),
                        "notes": st.column_config.TextColumn("Notes"),
                    },
                    disabled=["calculated_cost", "final_cost"],
                )
            else:
                st.info("No labor tasks are available for the selected project type.")
        elif labor_method == "crew_day":
            crew_day_cost = st.number_input("Crew day cost", min_value=0.0, value=1200.0, step=50.0)
            estimated_crew_days = st.number_input("Estimated crew days", min_value=0.0, value=1.0, step=0.25)
            manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0)
            override_reason = st.text_input("Override reason")
        elif labor_method == "hourly":
            estimated_labor_hours = st.number_input("Estimated labor hours", min_value=0.0, value=8.0, step=1.0)
            burdened_hourly_rate = st.number_input("Burdened hourly rate", min_value=0.0, value=85.0, step=5.0)
            manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0)
            override_reason = st.text_input("Override reason")
        else:
            subcontractor_quote_amount = st.number_input("Subcontractor quote amount", min_value=0.0, value=2500.0, step=50.0)
            project_management_markup_percent = st.number_input("Project management markup percent", min_value=0.0, value=0.10, step=0.01)
            manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0)
            override_reason = st.text_input("Override reason")

        st.subheader("Other costs and pricing")
        permit_cost = st.number_input("Permit cost", min_value=0.0, value=0.0, step=50.0)
        disposal_cost = st.number_input("Disposal cost", min_value=0.0, value=0.0, step=50.0)
        equipment_cost = st.number_input("Equipment cost", min_value=0.0, value=0.0, step=50.0)
        overhead_cost = st.number_input("Overhead cost", min_value=0.0, value=0.0, step=50.0)
        target_margin = st.number_input("Target margin", min_value=0.0, max_value=0.95, value=0.40, step=0.01)
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=0.20, value=0.0, step=0.01)
        calculate_clicked = st.form_submit_button("Calculate Labor")

    if calculate_clicked:
        material_cost = calculate_material_cost(measured_quantity, material_unit_cost, waste_factor)
        material_line_items = [
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
            }
        ]

        if labor_method == "unit_based":
            labor_line_items = _calculate_unit_based_labor(unit_based_rows, trade)
        elif labor_method == "crew_day":
            labor_result = calculate_crew_day_labor(
                crew_day_cost=crew_day_cost,
                estimated_days=estimated_crew_days,
                complexity_multiplier=final_multiplier,
                manual_override_cost=manual_override_cost if manual_override_cost > 0 else None,
            )
            labor_line_items = [
                {
                    "trade": trade,
                    "labor_method": labor_method,
                    "task_name": "Crew day labor",
                    "quantity": estimated_crew_days,
                    "unit": "day",
                    "base_rate": crew_day_cost,
                    "complexity_multiplier": final_multiplier,
                    "minimum_charge": 0.0,
                    "calculated_cost": labor_result["calculated_cost"],
                    "manual_override_cost": manual_override_cost if manual_override_cost > 0 else None,
                    "final_cost": labor_result["final_cost"],
                    "override_reason": override_reason,
                    "notes": "",
                    "manual_override_applied": labor_result["manual_override_applied"],
                    "minimum_charge_applied": labor_result["minimum_charge_applied"],
                }
            ]
        elif labor_method == "hourly":
            labor_result = calculate_hourly_labor(
                labor_hours=estimated_labor_hours,
                burdened_hourly_rate=burdened_hourly_rate,
                complexity_multiplier=final_multiplier,
                manual_override_cost=manual_override_cost if manual_override_cost > 0 else None,
            )
            labor_line_items = [
                {
                    "trade": trade,
                    "labor_method": labor_method,
                    "task_name": "Hourly labor",
                    "quantity": estimated_labor_hours,
                    "unit": "hour",
                    "base_rate": burdened_hourly_rate,
                    "complexity_multiplier": final_multiplier,
                    "minimum_charge": 0.0,
                    "calculated_cost": labor_result["calculated_cost"],
                    "manual_override_cost": manual_override_cost if manual_override_cost > 0 else None,
                    "final_cost": labor_result["final_cost"],
                    "override_reason": override_reason,
                    "notes": "",
                    "manual_override_applied": labor_result["manual_override_applied"],
                    "minimum_charge_applied": labor_result["minimum_charge_applied"],
                }
            ]
        else:
            labor_result = calculate_subcontractor_labor(
                subcontractor_quote_amount=subcontractor_quote_amount,
                project_management_markup_percent=project_management_markup_percent,
                manual_override_cost=manual_override_cost if manual_override_cost > 0 else None,
            )
            calculated_cost = labor_result["calculated_cost"]
            labor_line_items = [
                {
                    "trade": trade,
                    "labor_method": labor_method,
                    "task_name": "Subcontractor quote",
                    "quantity": 1.0,
                    "unit": "job",
                    "base_rate": subcontractor_quote_amount,
                    "complexity_multiplier": 1.0,
                    "minimum_charge": 0.0,
                    "calculated_cost": calculated_cost,
                    "manual_override_cost": manual_override_cost if manual_override_cost > 0 else None,
                    "final_cost": labor_result["final_cost"],
                    "override_reason": override_reason,
                    "notes": f"Project management markup: {project_management_markup_percent:.2%}",
                    "manual_override_applied": labor_result["manual_override_applied"],
                    "minimum_charge_applied": labor_result["minimum_charge_applied"],
                }
            ]

        totals = calculate_quote_totals(
            material_line_items,
            permit_cost,
            disposal_cost,
            equipment_cost,
            overhead_cost,
            target_margin,
            tax_rate,
            labor_line_items=labor_line_items,
        )
        labor_summary = calculate_labor_summary(labor_line_items)
        labor_confidence_level, labor_reasons = _labor_confidence(
            {
                "measured_quantity": measured_quantity,
                "selected_conditions": selected_conditions,
            },
            labor_line_items,
            trade,
        )

        st.session_state.quote_draft = {
            "quote_name": quote_name,
            "project_id": selected_project.id,
            "trade": trade,
            "material": material,
            "material_unit_cost": material_unit_cost,
            "material_line_items": material_line_items,
            "labor_line_items": labor_line_items,
            "totals": totals,
            "permit_cost": permit_cost,
            "disposal_cost": disposal_cost,
            "equipment_cost": equipment_cost,
            "overhead_cost": overhead_cost,
            "target_margin": target_margin,
            "tax_rate": tax_rate,
            "labor_method": labor_method,
            "measured_quantity": measured_quantity,
            "unit": quantity_unit,
            "difficulty_label": difficulty_label,
            "final_multiplier": final_multiplier,
            "labor_confidence_level": labor_confidence_level,
            "labor_reasons": labor_reasons,
            "labor_summary": labor_summary,
            "stories": stories,
            "access_label": access_label,
            "selected_conditions": selected_conditions,
        }

    draft = st.session_state.quote_draft
    if draft:
        material_cost = draft["totals"]["material_cost"]
        labor_cost = draft["totals"]["labor_cost"]
        total_cost = draft["totals"]["total_cost"]
        customer_price = draft["totals"]["customer_price"]
        labor_summary = draft["labor_summary"]
        st.subheader("Calculated quote")
        cols = st.columns(4)
        cols[0].metric("Material cost", f"${material_cost:,.2f}")
        cols[1].metric("Labor cost", f"${labor_cost:,.2f}")
        cols[2].metric("Total cost", f"${total_cost:,.2f}")
        cols[3].metric("Customer price", f"${customer_price:,.2f}")

        summary_cols = st.columns(5)
        summary_cols[0].metric("Base labor total", f"${labor_summary['base_labor_total']:,.2f}")
        summary_cols[1].metric("Adjusted labor total", f"${labor_summary['adjusted_labor_total']:,.2f}")
        summary_cols[2].metric("Override total", f"${labor_summary['manual_override_total']:,.2f}")
        summary_cols[3].metric("Minimum charge adj.", f"${labor_summary['minimum_charge_adjustment_total']:,.2f}")
        summary_cols[4].metric("Final labor total", f"${labor_summary['final_labor_total']:,.2f}")

        if draft["measured_quantity"] > 0:
            labor_per_unit = draft["totals"]["labor_cost"] / draft["measured_quantity"]
            st.caption(f"Labor cost per measured unit: ${labor_per_unit:,.2f}")

        if draft["labor_confidence_level"] == "high_confidence":
            st.success("Labor estimate looks complete based on selected quantity, labor tasks, and difficulty.")
        else:
            st.warning("Labor estimate needs review before quote approval.")
            for reason in draft["labor_reasons"]:
                st.write(f"- {reason}")

        labor_breakdown_df = pd.DataFrame(draft["labor_line_items"])
        if labor_breakdown_df.empty:
            st.info("No labor line items were calculated.")
        else:
            st.dataframe(
                labor_breakdown_df[
                    [
                        "task_name",
                        "quantity",
                        "unit",
                        "base_rate",
                        "complexity_multiplier",
                        "calculated_cost",
                        "manual_override_cost",
                        "final_cost",
                        "override_reason",
                        "notes",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        if st.button("Save Quote"):
            quote = Quote(
                project_id=draft["project_id"],
                quote_name=draft["quote_name"],
                status="draft",
                target_margin=draft["target_margin"],
                tax_rate=draft["tax_rate"],
                permit_cost=draft["permit_cost"],
                disposal_cost=draft["disposal_cost"],
                equipment_cost=draft["equipment_cost"],
                overhead_cost=draft["overhead_cost"],
                material_cost=draft["totals"]["material_cost"],
                labor_cost=draft["totals"]["labor_cost"],
                total_cost=draft["totals"]["total_cost"],
                customer_price=draft["totals"]["customer_price"],
            )
            db.add(quote)
            db.flush()
            for item in draft["material_line_items"]:
                db.add(QuoteLineItem(quote_id=quote.id, **item))
            for item in draft["labor_line_items"]:
                db.add(
                    QuoteLaborLineItem(
                        quote_id=quote.id,
                        trade=item["trade"],
                        labor_method=item["labor_method"],
                        task_name=item["task_name"],
                        quantity=item["quantity"],
                        unit=item["unit"],
                        base_rate=item["base_rate"],
                        complexity_multiplier=item["complexity_multiplier"],
                        minimum_charge=item["minimum_charge"],
                        calculated_cost=item["calculated_cost"],
                        manual_override_cost=item["manual_override_cost"],
                        final_cost=item["final_cost"],
                        override_reason=item["override_reason"],
                        notes=item["notes"],
                    )
                )
            db.commit()
            st.success(f"Quote {quote.id} saved.")
            st.session_state.quote_draft = None
            st.rerun()
finally:
    db.close()
