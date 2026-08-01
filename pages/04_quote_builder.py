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
    LaborTask,
    Material,
    MaterialPrice,
    Project,
    Quote,
    QuoteLaborLineItem,
    QuoteLineItem,
    TakeoffMeasurement,
)
from src.pricing_engine import (
    calculate_final_complexity_multiplier,
    calculate_labor_cost,
    calculate_labor_summary,
    calculate_material_cost,
    calculate_quote_totals,
    calculate_crew_day_labor,
    calculate_hourly_labor,
    calculate_subcontractor_labor,
)
from src.takeoff_extraction_service import link_quote_measurements


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


def _takeoff_measurement_label(measurement: TakeoffMeasurement) -> str:
    source_bits = [f"{measurement.measurement_type}", f"{measurement.quantity:g} {measurement.unit}"]
    if measurement.blueprint_sheet:
        sheet_label = measurement.blueprint_sheet.sheet_number or measurement.blueprint_sheet.sheet_name or f"Page {measurement.blueprint_sheet.page_number}"
        source_bits.append(sheet_label)
    if measurement.blueprint_file:
        source_bits.append(measurement.blueprint_file.original_file_name)
    return " | ".join(source_bits)


def _default_takeoff_measurements(trade: str, measurements: list[TakeoffMeasurement]) -> list[TakeoffMeasurement]:
    if trade == "roofing":
        relevant_types = {"roof_area"}
    else:
        relevant_types = {"siding_wall_area", "gable_area"}
    return [item for item in measurements if item.measurement_type in relevant_types]


def _calculate_takeoff_quantity(trade: str, measurements: list[TakeoffMeasurement]) -> dict:
    total_square_feet = 0.0
    used_measurements: list[dict] = []
    for measurement in measurements:
        quantity = float(measurement.quantity or 0)
        if quantity <= 0:
            continue
        if trade == "roofing" and measurement.measurement_type == "roof_area":
            if measurement.unit == "square_foot":
                square_feet = quantity
                quantity_in_squares = quantity / 100
            elif measurement.unit == "square":
                square_feet = quantity * 100
                quantity_in_squares = quantity
            else:
                square_feet = quantity
                quantity_in_squares = quantity
            total_square_feet += square_feet
            used_measurements.append(
                {
                    "id": measurement.id,
                    "measurement_type": measurement.measurement_type,
                    "quantity": quantity,
                    "unit": measurement.unit,
                    "square_feet": square_feet,
                    "squares": quantity_in_squares,
                }
            )
        elif trade == "siding" and measurement.measurement_type in {"siding_wall_area", "gable_area"}:
            if measurement.unit == "square_foot":
                square_feet = quantity
            elif measurement.unit == "square":
                square_feet = quantity * 100
            else:
                square_feet = quantity
            total_square_feet += square_feet
            used_measurements.append(
                {
                    "id": measurement.id,
                    "measurement_type": measurement.measurement_type,
                    "quantity": quantity,
                    "unit": measurement.unit,
                    "square_feet": square_feet,
                    "squares": square_feet / 100,
                }
            )
    total_squares = round(total_square_feet / 100, 2)
    return {
        "total_square_feet": round(total_square_feet, 2),
        "total_squares": total_squares,
        "used_measurements": used_measurements,
    }


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


def _trade_display_name(trade: str) -> str:
    return trade.replace("_", " ").title()


def _image_extraction_reference(project_id: int, trade: str) -> dict | None:
    draft = st.session_state.get("latest_image_measurement_extraction")
    if not draft:
        return None
    if draft.get("project_id") != project_id or draft.get("trade") != trade:
        return None
    return draft


def _image_measurement_table(extraction: dict) -> pd.DataFrame:
    rows = []
    for item in extraction.get("detected_measurements", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Label": item.get("label") or "",
                "Measurement Type": item.get("measurement_type") or "",
                "Shape": item.get("shape") or "",
                "Quantity": item.get("quantity"),
                "Confidence": item.get("confidence"),
            }
        )
    if not rows:
        rows = [{"Label": "", "Measurement Type": "", "Shape": "", "Quantity": None, "Confidence": None}]
    return pd.DataFrame(rows)


def _render_trade_section(db, selected_project: Project, trade: str, section_key: str) -> dict:
    approved_measurements = (
        db.query(TakeoffMeasurement)
        .filter(
            TakeoffMeasurement.project_id == selected_project.id,
            TakeoffMeasurement.trade == trade,
            TakeoffMeasurement.approved.is_(True),
        )
        .order_by(TakeoffMeasurement.created_at.desc())
        .all()
    )
    materials = db.query(Material).filter(Material.trade == trade, Material.active.is_(True)).order_by(Material.name).all()
    labor_tasks = _filtered_labor_tasks(db, trade, selected_project.project_type)
    if trade == "siding":
        siding_materials = [m for m in materials if m.unit == "square"]
        if siding_materials:
            materials = siding_materials

    if not materials or not labor_tasks:
        st.warning(f"Seed or add materials and labor tasks for {_trade_display_name(trade)}.")
        return {"included": False, "trade": trade}

    material_options = {m.name: m for m in materials}
    st.markdown(f"##### {_trade_display_name(trade)} scope")
    st.caption("Start with the scope and quantity. Labor settings are tucked below unless you need to adjust them.")
    extraction_reference = _image_extraction_reference(selected_project.id, trade)
    if extraction_reference:
        with st.expander("Latest image measurements", expanded=False):
            st.caption(
                f"Reference only. Enter these numbers manually in the quote. Image: {extraction_reference.get('image_name')}"
            )
            st.dataframe(
                _image_measurement_table(extraction_reference["extraction"]),
                use_container_width=True,
                hide_index=True,
            )
    default_takeoff_measurements = _default_takeoff_measurements(trade, approved_measurements)
    quantity_source = st.radio(
        "How should we get the quantity?",
        ["manual", "approved_takeoff"],
        horizontal=True,
        index=1 if default_takeoff_measurements else 0,
        key=f"{section_key}_quantity_source",
    )
    quantity_unit_options = ["square", "square_foot", "linear_foot", "each", "job", "allowance"]
    if quantity_source == "manual":
        quantity_cols = st.columns(2)
        measured_quantity = quantity_cols[0].number_input(
            "Quantity",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key=f"{section_key}_measured_quantity",
        )
        quantity_unit = quantity_cols[1].selectbox(
            "Unit",
            quantity_unit_options,
            key=f"{section_key}_quantity_unit",
        )
        selected_takeoff_measurements: list[TakeoffMeasurement] = []
        takeoff_summary = None
    else:
        quantity_unit = st.selectbox(
            "Unit",
            quantity_unit_options,
            index=0,
            disabled=True,
            key=f"{section_key}_quantity_unit",
        )
        if approved_measurements:
            selected_takeoff_measurements = st.multiselect(
                "Approved measurements to use",
                approved_measurements,
                format_func=_takeoff_measurement_label,
                default=default_takeoff_measurements,
                key=f"{section_key}_takeoff_measurements",
            )
            if selected_takeoff_measurements:
                takeoff_summary = _calculate_takeoff_quantity(trade, selected_takeoff_measurements)
                measured_quantity = takeoff_summary["total_squares"]
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Measurement Type": item["measurement_type"],
                                "Quantity": item["quantity"],
                                "Unit": item["unit"],
                                "Square Feet": item["square_feet"],
                                "Squares": item["squares"],
                            }
                            for item in takeoff_summary["used_measurements"]
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    f"Approved takeoff quantity: {takeoff_summary['total_square_feet']:,.2f} sq ft "
                    f"({takeoff_summary['total_squares']:,.2f} squares)"
                )
                st.caption("Approved takeoff measurements are preselected. Switch to manual if you want to enter the quantity yourself.")
            else:
                takeoff_summary = {"total_square_feet": 0.0, "total_squares": 0.0, "used_measurements": []}
                measured_quantity = 0.0
                st.info("Select one or more approved measurements to populate the quote quantity.")
        else:
            selected_takeoff_measurements = []
            takeoff_summary = {"total_square_feet": 0.0, "total_squares": 0.0, "used_measurements": []}
            measured_quantity = 0.0
            st.info("No approved measurements are available for this project and trade.")

    stories = st.number_input("Stories", min_value=0.0, value=1.0, step=1.0, key=f"{section_key}_stories")
    material = material_options[st.selectbox("Material", list(material_options), key=f"{section_key}_material")]
    latest_price = (
        db.query(MaterialPrice)
        .filter(MaterialPrice.material_id == material.id)
        .order_by(MaterialPrice.effective_date.desc())
        .first()
    )
    material_unit_cost = latest_price.unit_cost if latest_price else 0.0
    waste_factor = st.number_input(
        "Waste factor",
        min_value=0.0,
        value=float(material.default_waste_factor),
        step=0.01,
        key=f"{section_key}_waste_factor",
    )
    labor_method = "unit_based"
    difficulty_label = "simple"
    selected_conditions: list[str] = []
    final_multiplier = 1.0
    with st.expander("Labor settings", expanded=False):
        st.caption("Most jobs can stay on the default labor method and complexity. Change these only when the job calls for it.")
        labor_method_label = st.selectbox(
            "How should labor be priced?",
            list(LABOR_METHOD_LABELS.values()),
            key=f"{section_key}_labor_method",
        )
        labor_method = next(code for code, label in LABOR_METHOD_LABELS.items() if label == labor_method_label)
        difficulty_label = st.selectbox(
            "How hard is the job?",
            list(LABOR_DIFFICULTY_MULTIPLIERS.keys()),
            key=f"{section_key}_difficulty",
        )
        base_difficulty_multiplier = LABOR_DIFFICULTY_MULTIPLIERS[difficulty_label]
        condition_options = LABOR_CONDITION_MULTIPLIERS.get(trade, {})
        selected_conditions = [
            condition_name
            for condition_name in condition_options
            if st.checkbox(condition_name.replace("_", " ").title(), key=f"{section_key}_condition_{condition_name}")
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
    st.caption(f"Quantity source: {quantity_source}")
    if quantity_source == "approved_takeoff" and takeoff_summary is not None:
        st.caption(
            f"Takeoff source: {takeoff_summary['total_square_feet']:,.2f} sq ft / {takeoff_summary['total_squares']:,.2f} squares"
        )

    unit_based_rows = pd.DataFrame()
    if labor_method == "unit_based":
        default_rows = _default_unit_based_rows(labor_tasks, measured_quantity, final_multiplier)
        if not default_rows.empty:
            unit_based_rows = st.data_editor(
                default_rows,
                use_container_width=True,
                num_rows="dynamic",
                key=f"{section_key}_unit_based_labor_editor",
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
        crew_day_cost = st.number_input("Crew day cost", min_value=0.0, value=1200.0, step=50.0, key=f"{section_key}_crew_day_cost")
        estimated_crew_days = st.number_input("Estimated crew days", min_value=0.0, value=1.0, step=0.25, key=f"{section_key}_crew_days")
        manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0, key=f"{section_key}_crew_override")
        override_reason = st.text_input("Override reason", key=f"{section_key}_crew_reason")
    elif labor_method == "hourly":
        estimated_labor_hours = st.number_input("Estimated labor hours", min_value=0.0, value=8.0, step=1.0, key=f"{section_key}_hours")
        burdened_hourly_rate = st.number_input("Burdened hourly rate", min_value=0.0, value=85.0, step=5.0, key=f"{section_key}_hourly_rate")
        manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0, key=f"{section_key}_hourly_override")
        override_reason = st.text_input("Override reason", key=f"{section_key}_hourly_reason")
    else:
        subcontractor_quote_amount = st.number_input("Subcontractor quote amount", min_value=0.0, value=2500.0, step=50.0, key=f"{section_key}_sub_quote")
        project_management_markup_percent = st.number_input(
            "Project management markup percent",
            min_value=0.0,
            value=0.10,
            step=0.01,
            key=f"{section_key}_sub_markup",
        )
        manual_override_cost = st.number_input("Manual override cost", min_value=0.0, value=0.0, step=50.0, key=f"{section_key}_sub_override")
        override_reason = st.text_input("Override reason", key=f"{section_key}_sub_reason")

    return {
        "included": True,
        "trade": trade,
        "quote_name": f"{selected_project.project_name} Quote",
        "project_id": selected_project.id,
        "material": material,
        "material_unit_cost": material_unit_cost,
        "waste_factor": waste_factor,
        "material_line_items": [],
        "labor_tasks": labor_tasks,
        "labor_line_items": [],
        "totals": {},
        "permit_cost": 0.0,
        "disposal_cost": 0.0,
        "equipment_cost": 0.0,
        "overhead_cost": 0.0,
        "target_margin": 0.40,
        "tax_rate": 0.0,
        "labor_method": labor_method,
        "measured_quantity": measured_quantity,
        "unit": quantity_unit,
        "quantity_source": quantity_source,
        "takeoff_summary": takeoff_summary,
        "takeoff_measurement_ids": [item.id for item in selected_takeoff_measurements] if quantity_source == "approved_takeoff" else [],
        "quantity_note": "",
        "difficulty_label": difficulty_label,
        "final_multiplier": final_multiplier,
        "labor_confidence_level": "needs_review",
        "labor_reasons": [],
        "labor_summary": {},
        "stories": stories,
        "access_label": access_label,
        "selected_conditions": selected_conditions,
        "unit_based_rows": unit_based_rows,
        "crew_day_cost": locals().get("crew_day_cost"),
        "estimated_crew_days": locals().get("estimated_crew_days"),
        "hourly_labor_hours": locals().get("estimated_labor_hours"),
        "burdened_hourly_rate": locals().get("burdened_hourly_rate"),
        "subcontractor_quote_amount": locals().get("subcontractor_quote_amount"),
        "project_management_markup_percent": locals().get("project_management_markup_percent"),
        "manual_override_cost": locals().get("manual_override_cost"),
        "override_reason": locals().get("override_reason", ""),
    }


def _calculate_trade_section(section: dict) -> dict:
    trade = section["trade"]
    material = section["material"]
    material_unit_cost = section["material_unit_cost"]
    measured_quantity = float(section["measured_quantity"] or 0)
    waste_factor = float(section.get("waste_factor", material.default_waste_factor) if isinstance(section.get("waste_factor"), (int, float)) else material.default_waste_factor)
    if trade == "siding" and section["quantity_source"] == "approved_takeoff" and section.get("takeoff_summary") is not None:
        measured_quantity = section["takeoff_summary"]["total_squares"]
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

    labor_method = section["labor_method"]
    final_multiplier = section["final_multiplier"]
    if labor_method == "unit_based":
        labor_line_items = _calculate_unit_based_labor(section["unit_based_rows"], trade)
    elif labor_method == "crew_day":
        labor_result = calculate_crew_day_labor(
            crew_day_cost=section["crew_day_cost"],
            estimated_days=section["estimated_crew_days"],
            complexity_multiplier=final_multiplier,
            manual_override_cost=section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
        )
        labor_line_items = [
            {
                "trade": trade,
                "labor_method": labor_method,
                "task_name": "Crew day labor",
                "quantity": section["estimated_crew_days"],
                "unit": "day",
                "base_rate": section["crew_day_cost"],
                "complexity_multiplier": final_multiplier,
                "minimum_charge": 0.0,
                "calculated_cost": labor_result["calculated_cost"],
                "manual_override_cost": section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
                "final_cost": labor_result["final_cost"],
                "override_reason": section["override_reason"],
                "notes": "",
                "manual_override_applied": labor_result["manual_override_applied"],
                "minimum_charge_applied": labor_result["minimum_charge_applied"],
            }
        ]
    elif labor_method == "hourly":
        labor_result = calculate_hourly_labor(
            labor_hours=section["hourly_labor_hours"],
            burdened_hourly_rate=section["burdened_hourly_rate"],
            complexity_multiplier=final_multiplier,
            manual_override_cost=section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
        )
        labor_line_items = [
            {
                "trade": trade,
                "labor_method": labor_method,
                "task_name": "Hourly labor",
                "quantity": section["hourly_labor_hours"],
                "unit": "hour",
                "base_rate": section["burdened_hourly_rate"],
                "complexity_multiplier": final_multiplier,
                "minimum_charge": 0.0,
                "calculated_cost": labor_result["calculated_cost"],
                "manual_override_cost": section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
                "final_cost": labor_result["final_cost"],
                "override_reason": section["override_reason"],
                "notes": "",
                "manual_override_applied": labor_result["manual_override_applied"],
                "minimum_charge_applied": labor_result["minimum_charge_applied"],
            }
        ]
    else:
        labor_result = calculate_subcontractor_labor(
            subcontractor_quote_amount=section["subcontractor_quote_amount"],
            project_management_markup_percent=section["project_management_markup_percent"],
            manual_override_cost=section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
        )
        labor_line_items = [
            {
                "trade": trade,
                "labor_method": labor_method,
                "task_name": "Subcontractor quote",
                "quantity": 1.0,
                "unit": "job",
                "base_rate": section["subcontractor_quote_amount"],
                "complexity_multiplier": 1.0,
                "minimum_charge": 0.0,
                "calculated_cost": labor_result["calculated_cost"],
                "manual_override_cost": section["manual_override_cost"] if section["manual_override_cost"] > 0 else None,
                "final_cost": labor_result["final_cost"],
                "override_reason": section["override_reason"],
                "notes": f"Project management markup: {section['project_management_markup_percent']:.2%}",
                "manual_override_applied": labor_result["manual_override_applied"],
                "minimum_charge_applied": labor_result["minimum_charge_applied"],
            }
        ]

    totals = calculate_quote_totals(
        material_line_items,
        0.0,
        0.0,
        0.0,
        0.0,
        0.40,
        0.0,
        labor_line_items=labor_line_items,
    )
    labor_summary = calculate_labor_summary(labor_line_items)
    labor_confidence_level, labor_reasons = _labor_confidence(
        {
            "measured_quantity": measured_quantity,
            "selected_conditions": section["selected_conditions"],
        },
        labor_line_items,
        trade,
    )
    if section["quantity_source"] == "approved_takeoff" and section.get("takeoff_summary") is not None:
        quantity_note = (
            f"Quantity source: approved_takeoff; blueprint measurements: {', '.join(str(item) for item in section['takeoff_measurement_ids']) or 'none'}; "
            f"{section['takeoff_summary']['total_square_feet']:.2f} sq ft / {section['takeoff_summary']['total_squares']:.2f} squares."
        )
    else:
        quantity_note = f"Quantity source: manual; measured quantity entered directly as {measured_quantity:.2f} {section['unit']}."

    return {
        **section,
        "material_line_items": material_line_items,
        "labor_line_items": labor_line_items,
        "totals": totals,
        "labor_summary": labor_summary,
        "labor_confidence_level": labor_confidence_level,
        "labor_reasons": labor_reasons,
        "quantity_note": quantity_note,
    }


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
    if "quote_draft" not in st.session_state:
        st.session_state.quote_draft = None

    if selected_project.trade_scope == "combination":
        st.info("Combination jobs now default to both roofing and siding in one quote. Uncheck a section if it is not needed.")
        active_trades = [
            trade
            for trade in TRADES
            if st.checkbox(f"Include {_trade_display_name(trade)} scope", value=True, key=f"include_{trade}")
        ]
    else:
        active_trades = [selected_project.trade_scope]

    shared_cols = st.columns(4)
    permit_cost = shared_cols[0].number_input("Permit cost", min_value=0.0, value=0.0, step=50.0)
    disposal_cost = shared_cols[1].number_input("Disposal cost", min_value=0.0, value=0.0, step=50.0)
    equipment_cost = shared_cols[2].number_input("Equipment cost", min_value=0.0, value=0.0, step=50.0)
    overhead_cost = shared_cols[3].number_input("Overhead cost", min_value=0.0, value=0.0, step=50.0)
    pricing_cols = st.columns(2)
    target_margin = pricing_cols[0].number_input("Target margin", min_value=0.0, max_value=0.95, value=0.40, step=0.01)
    tax_rate = pricing_cols[1].number_input("Tax rate", min_value=0.0, max_value=0.20, value=0.0, step=0.01)

    if "quote_draft" not in st.session_state:
        st.session_state.quote_draft = None

    with st.form("quote_builder"):
        st.subheader("Labor Estimate")
        quote_name = st.text_input("Quote name", value=f"{selected_project.project_name} Quote")
        section_inputs = []
        for trade in active_trades:
            with st.expander(f"{_trade_display_name(trade)} scope", expanded=True):
                section_inputs.append(_render_trade_section(db, selected_project, trade, trade))

        calculate_clicked = st.form_submit_button("Calculate Quote")

    if calculate_clicked:
        sections = [_calculate_trade_section(section) for section in section_inputs if section.get("included", True)]
        if not sections:
            st.warning("Select at least one trade section before calculating the quote.")
            st.stop()

        material_line_items: list[dict] = []
        labor_line_items: list[dict] = []
        section_summaries: list[dict] = []
        quantity_notes: list[str] = []
        labor_reasons: list[str] = []
        section_confidences: list[str] = []
        for section in sections:
            material_line_items.extend(section["material_line_items"])
            labor_line_items.extend(section["labor_line_items"])
            section_summaries.append(
                {
                    "trade": section["trade"],
                    "measured_quantity": section["measured_quantity"],
                    "unit": section["unit"],
                    "material_name": section["material"].name,
                    "stories": section["stories"],
                    "difficulty_label": section["difficulty_label"],
                    "access_label": section["access_label"],
                    "labor_summary": section["labor_summary"],
                    "labor_confidence_level": section["labor_confidence_level"],
                    "labor_reasons": section["labor_reasons"],
                    "labor_line_items": section["labor_line_items"],
                }
            )
            quantity_notes.append(section["quantity_note"])
            labor_reasons.extend([f"{_trade_display_name(section['trade'])}: {reason}" for reason in section["labor_reasons"]])
            section_confidences.append(section["labor_confidence_level"])

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
        labor_confidence_level = "high_confidence" if all(level == "high_confidence" for level in section_confidences) else "needs_review"
        if labor_confidence_level == "high_confidence":
            labor_reasons = ["Labor estimate looks complete based on selected quantity, labor tasks, and difficulty."]
        takeoff_ids = [item for section in sections for item in section["takeoff_measurement_ids"]]
        quantity_note = " | ".join(quantity_notes)

        st.session_state.quote_draft = {
            "quote_name": quote_name,
            "project_id": selected_project.id,
            "trade": "combination" if len(sections) > 1 else sections[0]["trade"],
            "material": material_line_items[0] if material_line_items else None,
            "material_unit_cost": 0.0,
            "material_line_items": material_line_items,
            "labor_line_items": labor_line_items,
            "totals": totals,
            "permit_cost": permit_cost,
            "disposal_cost": disposal_cost,
            "equipment_cost": equipment_cost,
            "overhead_cost": overhead_cost,
            "target_margin": target_margin,
            "tax_rate": tax_rate,
            "labor_method": "combination" if len(sections) > 1 else sections[0]["labor_method"],
            "measured_quantity": sum(float(section["measured_quantity"] or 0) for section in sections),
            "unit": "multiple" if len(sections) > 1 else sections[0]["unit"],
            "quantity_source": "combined" if len(sections) > 1 else sections[0]["quantity_source"],
            "quantity_note": quantity_note,
            "takeoff_measurement_ids": takeoff_ids,
            "difficulty_label": "combined" if len(sections) > 1 else sections[0]["difficulty_label"],
            "final_multiplier": None,
            "labor_confidence_level": labor_confidence_level,
            "labor_reasons": labor_reasons,
            "labor_summary": labor_summary,
            "stories": None,
            "access_label": None,
            "selected_conditions": [],
            "sections": section_summaries,
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

        if draft.get("sections"):
            for section in draft["sections"]:
                with st.expander(f"{_trade_display_name(section['trade'])} summary", expanded=True):
                    section_cols = st.columns(4)
                    section_cols[0].metric("Measured quantity", f"{float(section['measured_quantity'] or 0):,.2f}")
                    section_cols[1].metric("Trade", _trade_display_name(section["trade"]))
                    section_cols[2].metric("Tasks", str(len(section["labor_line_items"])))
                    section_cols[3].metric("Confidence", section["labor_confidence_level"].replace("_", " ").title())
                    st.caption(f"Material: {section['material_name']}")
                    st.caption(f"Difficulty: {section['difficulty_label']}")
                    st.caption(f"Access: {section['access_label']}")
                    section_labor_summary = section["labor_summary"]
                    section_summary_cols = st.columns(3)
                    section_summary_cols[0].metric("Base labor", f"${section_labor_summary['base_labor_total']:,.2f}")
                    section_summary_cols[1].metric("Final labor", f"${section_labor_summary['final_labor_total']:,.2f}")
                    section_summary_cols[2].metric("Unit", section["unit"])
                    section_labor_df = pd.DataFrame(section["labor_line_items"])
                    if not section_labor_df.empty:
                        st.dataframe(
                            section_labor_df[
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
                notes=draft["quantity_note"],
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
            if draft.get("takeoff_measurement_ids"):
                link_quote_measurements(db, quote.id, draft["takeoff_measurement_ids"])
            else:
                db.commit()
            st.success(f"Quote {quote.id} saved.")
            st.session_state.quote_draft = None
            st.rerun()
finally:
    db.close()
