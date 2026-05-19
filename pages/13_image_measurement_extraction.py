from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.blueprint_service import sanitize_filename
from src.constants import MEASUREMENT_IMAGE_TYPES
from src.database import SessionLocal, init_db
from src.models import Project
from src.openai_vision_service import extract_measurements_from_image


UPLOAD_DIR = Path("data/uploads/measurement_images")


def _save_uploaded_image(uploaded_file) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(uploaded_file.name)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name
    uploaded_file.seek(0)
    file_path.write_bytes(uploaded_file.getbuffer())
    return str(file_path)


def _measurement_table(extraction: dict) -> pd.DataFrame:
    rows = []
    for item in extraction.get("detected_measurements", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Label": item.get("label") or "",
                "Measurement Type": item.get("measurement_type") or "",
                "Shape": item.get("shape") or "",
                "Width (ft)": item.get("width_ft"),
                "Height (ft)": item.get("height_ft"),
                "Base (ft)": item.get("base_ft"),
                "Top Width (ft)": item.get("top_width_ft"),
                "Bottom Width (ft)": item.get("bottom_width_ft"),
                "Length (ft)": item.get("length_ft"),
                "Quantity": item.get("quantity"),
                "Confidence": item.get("confidence"),
                "Source Text": item.get("source_text") or "",
            }
        )
    if not rows:
        rows = [
            {
                "Label": "",
                "Measurement Type": "",
                "Shape": "",
                "Width (ft)": None,
                "Height (ft)": None,
                "Base (ft)": None,
                "Top Width (ft)": None,
                "Bottom Width (ft)": None,
                "Length (ft)": None,
                "Quantity": None,
                "Confidence": None,
                "Source Text": "",
            }
        ]
    return pd.DataFrame(rows)


def _opening_table(extraction: dict) -> pd.DataFrame:
    rows = []
    for item in extraction.get("openings", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Opening Type": item.get("opening_type") or "",
                "Quantity": item.get("quantity"),
                "Width (ft)": item.get("width_ft"),
                "Height (ft)": item.get("height_ft"),
                "Confidence": item.get("confidence"),
            }
        )
    if not rows:
        rows = [
            {
                "Opening Type": "",
                "Quantity": None,
                "Width (ft)": None,
                "Height (ft)": None,
                "Confidence": None,
            }
        ]
    return pd.DataFrame(rows)


def _store_latest_extraction(project_id: int, trade: str, image_name: str, image_path: str, extraction: dict) -> None:
    st.session_state["latest_image_measurement_extraction"] = {
        "project_id": project_id,
        "trade": trade,
        "image_name": image_name,
        "image_path": image_path,
        "extraction": extraction,
    }


require_auth()
st.title("Image Measurement Extraction")
init_db()
db = SessionLocal()
try:
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    if not projects:
        st.warning("Create a project before extracting image measurements.")
        st.stop()

    project_options = {f"{project.project_name} - {project.customer.name} ({project.id})": project for project in projects}
    selected_project = project_options[st.selectbox("Project", list(project_options))]
    trade = st.selectbox("Trade", ["roofing", "siding"])

    st.warning(
        "AI extracted measurements are reference only. Review them and enter the final quantities in Quote Builder."
    )

    uploaded_image = st.file_uploader("Upload image", type=MEASUREMENT_IMAGE_TYPES)
    if uploaded_image is not None:
        current_signature = (uploaded_image.name, uploaded_image.size)
        if st.session_state.get("measurement_image_signature") != current_signature:
            saved_path = _save_uploaded_image(uploaded_image)
            st.session_state["measurement_image_signature"] = current_signature
            st.session_state["measurement_image_path"] = saved_path
            st.session_state["measurement_image_name"] = uploaded_image.name
            st.session_state["measurement_image_project_id"] = selected_project.id
            st.session_state["measurement_image_trade"] = trade
            st.session_state.pop("latest_image_measurement_extraction", None)
        st.caption(f"Saved image: {st.session_state.get('measurement_image_path')}")
        st.image(st.session_state.get("measurement_image_path"), caption=uploaded_image.name, use_container_width=True)

    image_path = st.session_state.get("measurement_image_path")
    image_name = st.session_state.get("measurement_image_name") or "uploaded image"

    if st.button("Extract Measurements"):
        if not image_path:
            st.error("Upload an image before extracting measurements.")
        else:
            try:
                extraction = extract_measurements_from_image(image_path, trade_hint=trade)
            except RuntimeError as exc:
                st.error(str(exc))
            else:
                _store_latest_extraction(selected_project.id, trade, image_name, image_path, extraction)
                st.success("Measurements extracted. Use Quote Builder to enter the final quantities.")

    draft = st.session_state.get("latest_image_measurement_extraction")
    if draft and draft.get("project_id") == selected_project.id and draft.get("trade") == trade:
        extraction = draft["extraction"]
        measurements = extraction.get("detected_measurements", [])
        openings = extraction.get("openings", [])

        st.caption(f"Image: {draft.get('image_name')}")
        metrics = st.columns(4)
        metrics[0].metric("Confidence", f"{float(extraction.get('confidence') or 0):.2f}")
        metrics[1].metric("Measurements", str(len(measurements)))
        metrics[2].metric("Openings", str(len(openings)))
        metrics[3].metric("Warnings", str(len(extraction.get("warnings") or [])))

        if extraction.get("warnings"):
            st.warning("\n".join(f"- {warning}" for warning in extraction.get("warnings", [])))
        if extraction.get("calculation_recommendations"):
            st.info("\n".join(f"- {item}" for item in extraction.get("calculation_recommendations", [])))

        st.subheader("Extracted measurements")
        st.dataframe(_measurement_table(extraction), use_container_width=True, hide_index=True)

        st.subheader("Detected openings")
        st.dataframe(_opening_table(extraction), use_container_width=True, hide_index=True)

        with st.expander("Technical details", expanded=False):
            st.json(extraction)

        st.info("Use these measurements as reference when you complete the quote. Enter the final quantities in Quote Builder.")

        if st.button("Clear extraction"):
            st.session_state.pop("latest_image_measurement_extraction", None)
            st.session_state.pop("measurement_image_signature", None)
            st.session_state.pop("measurement_image_path", None)
            st.session_state.pop("measurement_image_name", None)
            st.session_state.pop("measurement_image_project_id", None)
            st.session_state.pop("measurement_image_trade", None)
            st.rerun()
    elif draft:
        st.info("There is a saved extraction for another project or trade. Switch to that project and trade to review it.")
finally:
    db.close()
