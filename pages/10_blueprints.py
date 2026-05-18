from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.blueprint_service import create_blueprint_sheets_from_pdf, extract_pdf_text, save_uploaded_blueprint
from src.database import SessionLocal, init_db
from src.models import BlueprintFile, BlueprintSheet, Project

require_auth()
st.title("Blueprints")
init_db()
db = SessionLocal()
try:
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    if not projects:
        st.warning("Create a project before uploading blueprints.")
        st.stop()

    project_options = {f"{project.project_name} - {project.customer.name} ({project.id})": project for project in projects}
    selected_project = project_options[st.selectbox("Project", list(project_options))]

    st.warning(
        "This feature extracts text and sheet metadata only. It does not yet perform automatic measurement takeoff. "
        "Measurements must be manually entered and approved before they affect a quote."
    )

    with st.form("upload_blueprint"):
        uploaded_file = st.file_uploader("Upload blueprint PDF", type=["pdf"])
        plan_version = st.text_input("Plan version")
        description = st.text_area("Description")
        notes = st.text_area("Notes")
        save_clicked = st.form_submit_button("Save blueprint")

    if save_clicked and uploaded_file is not None:
        upload_dir = Path(__file__).resolve().parents[1] / "data" / "uploads" / "blueprints"
        saved = save_uploaded_blueprint(uploaded_file, str(upload_dir))
        extracted = extract_pdf_text(saved["file_path"])
        blueprint_file = BlueprintFile(
            project_id=selected_project.id,
            original_file_name=saved["original_file_name"],
            stored_file_name=saved["stored_file_name"],
            file_path=saved["file_path"],
            file_type=saved["file_type"],
            file_size_bytes=saved["file_size_bytes"],
            plan_version=plan_version,
            description=description,
            extracted_text=extracted["full_text"],
            sheet_count=extracted["sheet_count"],
            notes=notes,
            is_active=True,
        )
        db.add(blueprint_file)
        db.flush()
        create_blueprint_sheets_from_pdf(db, blueprint_file.id, extracted["pages"])
        db.commit()
        st.success("Blueprint saved and sheets extracted.")
        st.rerun()

    st.subheader("Uploaded blueprints")
    blueprint_files = (
        db.query(BlueprintFile)
        .filter(BlueprintFile.project_id == selected_project.id)
        .order_by(BlueprintFile.uploaded_at.desc())
        .all()
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": blueprint.id,
                    "Original File": blueprint.original_file_name,
                    "Plan Version": blueprint.plan_version,
                    "Description": blueprint.description,
                    "Sheet Count": blueprint.sheet_count,
                    "Uploaded": blueprint.uploaded_at,
                    "Active": blueprint.is_active,
                    "File Path": blueprint.file_path,
                }
                for blueprint in blueprint_files
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if blueprint_files:
        selected_blueprint = st.selectbox(
            "Detected sheet source",
            blueprint_files,
            format_func=lambda item: f"{item.original_file_name} ({item.id})",
        )
        sheets = (
            db.query(BlueprintSheet)
            .filter(BlueprintSheet.blueprint_file_id == selected_blueprint.id)
            .order_by(BlueprintSheet.page_number)
            .all()
        )
        st.subheader("Detected sheets")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Page": sheet.page_number,
                        "Sheet Number": sheet.sheet_number,
                        "Sheet Name": sheet.sheet_name,
                        "Sheet Type": sheet.sheet_type,
                        "Scale Text": sheet.scale_text,
                        "Confidence": sheet.confidence_score,
                        "Text Preview": (sheet.extracted_text or "")[:180],
                    }
                    for sheet in sheets
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
finally:
    db.close()
