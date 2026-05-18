from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import BlueprintFile, BlueprintSheet, Project, TakeoffMeasurement

require_auth()
st.title("Takeoff Measurements")
init_db()
db = SessionLocal()
try:
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    if not projects:
        st.warning("Create a project before entering takeoff measurements.")
        st.stop()

    project_options = {f"{project.project_name} - {project.customer.name} ({project.id})": project for project in projects}
    selected_project = project_options[st.selectbox("Project", list(project_options))]
    project_blueprints = (
        db.query(BlueprintFile)
        .filter(BlueprintFile.project_id == selected_project.id)
        .order_by(BlueprintFile.uploaded_at.desc())
        .all()
    )
    blueprint_options = {"None": None, **{f"{item.original_file_name} ({item.id})": item for item in project_blueprints}}
    selected_blueprint = blueprint_options[st.selectbox("Blueprint file", list(blueprint_options))]
    if selected_blueprint is not None:
        project_sheets = (
            db.query(BlueprintSheet)
            .filter(BlueprintSheet.blueprint_file_id == selected_blueprint.id)
            .order_by(BlueprintSheet.page_number)
            .all()
        )
        sheet_options = {"None": None, **{f"Page {sheet.page_number} - {sheet.sheet_name or sheet.sheet_type}": sheet for sheet in project_sheets}}
    else:
        project_sheets = []
        sheet_options = {"None": None}
    selected_sheet = sheet_options[st.selectbox("Blueprint sheet", list(sheet_options))]

    st.warning("Only approved measurements are available for quote calculations.")

    with st.form("takeoff_measurement"):
        trade = st.selectbox("Trade", ["roofing", "siding"])
        measurement_type = st.text_input("Measurement type")
        quantity = st.number_input("Quantity", min_value=0.0, value=0.0, step=1.0)
        unit = st.selectbox("Unit", ["square", "square_foot", "linear_foot", "each", "job", "allowance"])
        source = st.selectbox("Source", ["manual", "pdf_assisted", "field_measurement", "ai_suggested_future", "cad_extracted_future"])
        confidence_score = st.number_input("Confidence score", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
        approved = st.checkbox("Approved", value=False)
        approved_by = st.text_input("Approved by")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save measurement")
        if submitted and measurement_type:
            db.add(
                TakeoffMeasurement(
                    project_id=selected_project.id,
                    blueprint_file_id=getattr(selected_blueprint, "id", None),
                    blueprint_sheet_id=getattr(selected_sheet, "id", None),
                    trade=trade,
                    measurement_type=measurement_type,
                    quantity=quantity,
                    unit=unit,
                    source=source,
                    confidence_score=confidence_score,
                    approved=approved,
                    approved_by=approved_by or None,
                    notes=notes,
                )
            )
            db.commit()
            st.success("Measurement saved.")
            st.rerun()

    measurements = db.query(TakeoffMeasurement).filter(TakeoffMeasurement.project_id == selected_project.id).order_by(TakeoffMeasurement.created_at.desc()).all()
    filter_choice = st.radio("Filter", ["All measurements", "Approved only", "Unapproved only", "Roofing", "Siding"], horizontal=True)
    if filter_choice == "Approved only":
        measurements = [item for item in measurements if item.approved]
    elif filter_choice == "Unapproved only":
        measurements = [item for item in measurements if not item.approved]
    elif filter_choice == "Roofing":
        measurements = [item for item in measurements if item.trade == "roofing"]
    elif filter_choice == "Siding":
        measurements = [item for item in measurements if item.trade == "siding"]

    st.subheader("Takeoff measurements")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Trade": item.trade,
                    "Measurement Type": item.measurement_type,
                    "Quantity": item.quantity,
                    "Unit": item.unit,
                    "Source": item.source,
                    "Confidence": item.confidence_score,
                    "Approved": item.approved,
                    "Blueprint File": getattr(item.blueprint_file, "original_file_name", None),
                    "Sheet": getattr(item.blueprint_sheet, "sheet_name", None) or getattr(item.blueprint_sheet, "sheet_type", None),
                    "Notes": item.notes,
                }
                for item in measurements
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
