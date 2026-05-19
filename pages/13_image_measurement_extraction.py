from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.blueprint_service import sanitize_filename
from src.constants import (
    GENERAL_MEASUREMENT_TYPES,
    MEASUREMENT_IMAGE_TYPES,
    ROOFING_AREA_MEASUREMENT_TYPES,
    ROOFING_LINEAR_MEASUREMENT_TYPES,
    SIDING_AREA_MEASUREMENT_TYPES,
    SIDING_LINEAR_MEASUREMENT_TYPES,
)
from src.database import SessionLocal, init_db
from src.measurement_calculator import calculate_area_from_measurement, calculate_net_wall_area, calculate_total_opening_area, roofing_squares, siding_squares
from src.models import Project, TakeoffMeasurement
from src.openai_vision_service import extract_measurements_from_image


UPLOAD_DIR = Path("data/uploads/measurement_images")
AREA_SHAPES = {"rectangle", "triangle", "trapezoid"}


def _save_uploaded_image(uploaded_file) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(uploaded_file.name)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name
    uploaded_file.seek(0)
    file_path.write_bytes(uploaded_file.getbuffer())
    return str(file_path)


def _extraction_json_text(extraction: dict | None) -> str:
    if not extraction:
        return ""
    return json.dumps(extraction, indent=2, sort_keys=True)


def _parse_extraction_json(raw_text: str) -> dict:
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("Extraction JSON must be a JSON object.")
    return parsed


def _measurements_dataframe(measurements: list[dict]) -> pd.DataFrame:
    rows = []
    for measurement in measurements:
        row = dict(measurement)
        row.setdefault("include", True)
        row.setdefault("warnings", "")
        row.setdefault("calculated_area_sqft", None)
        rows.append(row)
    if not rows:
        rows = [
            {
                "include": False,
                "label": "",
                "measurement_type": "general_measurement",
                "shape": "unknown",
                "width_ft": None,
                "height_ft": None,
                "base_ft": None,
                "top_width_ft": None,
                "bottom_width_ft": None,
                "length_ft": None,
                "quantity": None,
                "confidence": 0.0,
                "source_text": "",
                "calculated_area_sqft": None,
                "warnings": "",
            }
        ]
    return pd.DataFrame(rows)


def _openings_dataframe(openings: list[dict]) -> pd.DataFrame:
    rows = [dict(opening) for opening in openings]
    if not rows:
        rows = [
            {
                "opening_type": "window",
                "quantity": 1.0,
                "width_ft": None,
                "height_ft": None,
                "confidence": 0.0,
            }
        ]
    return pd.DataFrame(rows)


def _blank_opening_row() -> dict:
    return {
        "opening_type": "window",
        "quantity": 1.0,
        "width_ft": None,
        "height_ft": None,
        "confidence": 0.0,
    }


def _normalize_editor_records(frame: pd.DataFrame) -> list[dict]:
    return frame.where(pd.notna(frame), None).replace("", None).to_dict("records")


def _measurement_options(trade: str, shape: str) -> list[str]:
    if trade == "roofing":
        options = ROOFING_AREA_MEASUREMENT_TYPES + ROOFING_LINEAR_MEASUREMENT_TYPES + GENERAL_MEASUREMENT_TYPES
        if shape == "count":
            options = ["roof_penetration_count"] + [item for item in options if item != "roof_penetration_count"]
        return options
    options = SIDING_AREA_MEASUREMENT_TYPES + SIDING_LINEAR_MEASUREMENT_TYPES + GENERAL_MEASUREMENT_TYPES
    return options


def _compute_preview(trade: str, measurements: list[dict], openings: list[dict], deduct_openings: bool) -> dict:
    preview_rows: list[dict] = []
    wall_area = 0.0
    gable_area = 0.0
    roof_area = 0.0
    linear_measurements: list[dict] = []
    warnings: list[str] = []

    for measurement in measurements:
        if not measurement.get("include"):
            continue
        area_result = calculate_area_from_measurement(measurement)
        area_sqft = area_result["area_sqft"]
        row_warnings = list(area_result["warnings"])
        measurement_type = str(measurement.get("measurement_type") or "").strip()
        shape = str(measurement.get("shape") or "unknown").strip().lower()
        if measurement_type in SIDING_AREA_MEASUREMENT_TYPES + ROOFING_AREA_MEASUREMENT_TYPES and area_sqft is None:
            row_warnings.append("Selected area measurement is missing dimensions.")
        if measurement_type in SIDING_LINEAR_MEASUREMENT_TYPES + ROOFING_LINEAR_MEASUREMENT_TYPES or measurement_type == "roof_penetration_count":
            if _row_quantity(measurement) is None:
                row_warnings.append("Selected linear measurement is missing a quantity or length.")
        preview_row = dict(measurement)
        preview_row["calculated_area_sqft"] = area_sqft
        preview_row["warnings"] = "; ".join(row_warnings)
        preview_rows.append(preview_row)
        warnings.extend(row_warnings)

        if trade == "siding":
            if measurement_type == "gable_area" and area_sqft is not None:
                gable_area += area_sqft
            elif measurement_type == "siding_wall_area" or shape in AREA_SHAPES:
                if area_sqft is not None:
                    wall_area += area_sqft
            elif measurement_type in SIDING_LINEAR_MEASUREMENT_TYPES:
                linear_measurements.append(preview_row)
        else:
            if measurement_type == "roof_area" or shape in AREA_SHAPES:
                if area_sqft is not None:
                    roof_area += area_sqft
            elif measurement_type in ROOFING_LINEAR_MEASUREMENT_TYPES or measurement_type == "roof_penetration_count":
                linear_measurements.append(preview_row)

    opening_area = calculate_total_opening_area(openings) if deduct_openings else 0.0
    net_wall_area = calculate_net_wall_area(wall_area, opening_area) if trade == "siding" else 0.0
    combined_area = roof_area if trade == "roofing" else net_wall_area + gable_area
    combined_area = round(combined_area, 2)
    combined_squares = round(roofing_squares(combined_area) if trade == "roofing" else siding_squares(combined_area), 2)

    return {
        "rows": preview_rows,
        "warnings": sorted(set(warnings)),
        "wall_area": round(wall_area, 2),
        "gable_area": round(gable_area, 2),
        "roof_area": round(roof_area, 2),
        "opening_area": round(opening_area, 2),
        "net_wall_area": round(net_wall_area, 2),
        "combined_area": combined_area,
        "combined_squares": combined_squares,
        "linear_measurements": linear_measurements,
    }


def _row_quantity(row: dict) -> float | None:
    for key in ("length_ft", "quantity"):
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _save_preview_measurements(
    db,
    project_id: int,
    image_name: str,
    trade: str,
    preview: dict,
    measurement_rows: list[dict],
    openings: list[dict],
    deduct_openings: bool,
    approved_by: str | None,
) -> list[TakeoffMeasurement]:
    saved: list[TakeoffMeasurement] = []
    opening_area = preview["opening_area"] if deduct_openings else 0.0
    confidence = 0.0
    if measurement_rows:
        confidence = max(float(row.get("confidence") or 0) for row in measurement_rows if row.get("include")) if any(row.get("include") for row in measurement_rows) else 0.0

    if trade == "siding":
        wall_rows = [
            row
            for row in preview["rows"]
            if row.get("include")
            and str(row.get("measurement_type")) == "siding_wall_area"
            and row.get("calculated_area_sqft") is not None
        ]
        gable_rows = [
            row
            for row in preview["rows"]
            if row.get("include")
            and str(row.get("measurement_type")) == "gable_area"
            and row.get("calculated_area_sqft") is not None
        ]
        if wall_rows:
            wall_area_total = round(sum(float(row["calculated_area_sqft"]) for row in wall_rows), 2)
            note = (
                f"Image: {image_name} | Gross wall area: {wall_area_total:.2f} sq ft | "
                f"Opening deduction: {opening_area:.2f} sq ft | AI confidence: {confidence:.2f}"
            )
            saved.append(
                TakeoffMeasurement(
                    project_id=project_id,
                    blueprint_file_id=None,
                    blueprint_sheet_id=None,
                    trade="siding",
                    measurement_type="siding_wall_area",
                    quantity=calculate_net_wall_area(wall_area_total, opening_area) if deduct_openings else wall_area_total,
                    unit="square_foot",
                    source="openai_vision_extracted",
                    confidence_score=confidence,
                    approved=True,
                    approved_by=approved_by or None,
                    notes=note,
                )
            )
        if gable_rows:
            gable_area_total = round(sum(float(row["calculated_area_sqft"]) for row in gable_rows), 2)
            note = f"Image: {image_name} | Gable area: {gable_area_total:.2f} sq ft | AI confidence: {confidence:.2f}"
            saved.append(
                TakeoffMeasurement(
                    project_id=project_id,
                    blueprint_file_id=None,
                    blueprint_sheet_id=None,
                    trade="siding",
                    measurement_type="gable_area",
                    quantity=gable_area_total,
                    unit="square_foot",
                    source="openai_vision_extracted",
                    confidence_score=confidence,
                    approved=True,
                    approved_by=approved_by or None,
                    notes=note,
                )
            )
        for row in preview["linear_measurements"]:
            quantity = _row_quantity(row)
            if quantity is None:
                continue
            measurement_type = str(row.get("measurement_type") or "").strip()
            if measurement_type not in SIDING_LINEAR_MEASUREMENT_TYPES:
                continue
            unit = "each" if measurement_type.endswith("_count") else "linear_foot"
            saved.append(
                TakeoffMeasurement(
                    project_id=project_id,
                    blueprint_file_id=None,
                    blueprint_sheet_id=None,
                    trade="siding",
                    measurement_type=measurement_type,
                    quantity=quantity,
                    unit=unit,
                    source="openai_vision_extracted",
                    confidence_score=float(row.get("confidence") or confidence),
                    approved=True,
                    approved_by=approved_by or None,
                    notes=f"Image: {image_name} | AI confidence: {float(row.get('confidence') or confidence):.2f}",
                )
            )
    else:
        roof_rows = [
            row
            for row in preview["rows"]
            if row.get("include")
            and str(row.get("measurement_type")) == "roof_area"
            and row.get("calculated_area_sqft") is not None
        ]
        if roof_rows:
            roof_area_total = round(sum(float(row["calculated_area_sqft"]) for row in roof_rows), 2)
            note = f"Image: {image_name} | Roof area: {roof_area_total:.2f} sq ft | AI confidence: {confidence:.2f}"
            saved.append(
                TakeoffMeasurement(
                    project_id=project_id,
                    blueprint_file_id=None,
                    blueprint_sheet_id=None,
                    trade="roofing",
                    measurement_type="roof_area",
                    quantity=roof_area_total,
                    unit="square_foot",
                    source="openai_vision_extracted",
                    confidence_score=confidence,
                    approved=True,
                    approved_by=approved_by or None,
                    notes=note,
                )
            )
        for row in preview["linear_measurements"]:
            quantity = _row_quantity(row)
            if quantity is None:
                continue
            measurement_type = str(row.get("measurement_type") or "").strip()
            if measurement_type not in ROOFING_LINEAR_MEASUREMENT_TYPES and measurement_type != "roof_penetration_count":
                continue
            unit = "each" if measurement_type.endswith("_count") else "linear_foot"
            saved.append(
                TakeoffMeasurement(
                    project_id=project_id,
                    blueprint_file_id=None,
                    blueprint_sheet_id=None,
                    trade="roofing",
                    measurement_type=measurement_type,
                    quantity=quantity,
                    unit=unit,
                    source="openai_vision_extracted",
                    confidence_score=float(row.get("confidence") or confidence),
                    approved=True,
                    approved_by=approved_by or None,
                    notes=f"Image: {image_name} | AI confidence: {float(row.get('confidence') or confidence):.2f}",
                )
            )

    for item in saved:
        db.add(item)
    db.commit()
    return saved


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
        "AI extracted measurements must be reviewed before use. Do not approve measurements unless the image is clear and the dimensions are verified."
    )

    uploaded_image = st.file_uploader("Upload image", type=MEASUREMENT_IMAGE_TYPES)
    if uploaded_image is not None:
        saved_path = _save_uploaded_image(uploaded_image)
        st.session_state["measurement_image_path"] = saved_path
        st.session_state["measurement_image_name"] = uploaded_image.name
        st.session_state["measurement_extraction"] = None
        st.session_state.pop("opening_editor_rows", None)
        st.caption(f"Saved image: {saved_path}")
        if uploaded_image.type.startswith("image/"):
            st.image(saved_path, caption=uploaded_image.name, use_container_width=True)

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
                st.session_state["measurement_extraction"] = extraction
                st.session_state["measurement_extraction_json"] = _extraction_json_text(extraction)
                st.session_state.pop("opening_editor_rows", None)
                st.success("Measurements extracted.")

    extraction = st.session_state.get("measurement_extraction")
    if extraction:
        st.caption(f"Extraction confidence: {float(extraction.get('confidence') or 0):.2f}")
        if extraction.get("warnings"):
            st.warning("\n".join(f"- {warning}" for warning in extraction.get("warnings", [])))
        if extraction.get("calculation_recommendations"):
            st.info("\n".join(f"- {item}" for item in extraction.get("calculation_recommendations", [])))

        with st.expander("Raw extraction JSON", expanded=False):
            st.code(_extraction_json_text(extraction), language="json")
            edited_json = st.text_area(
                "Edit raw JSON before saving",
                value=st.session_state.get("measurement_extraction_json", _extraction_json_text(extraction)),
                height=320,
                key="measurement_extraction_json_editor",
            )
            if st.button("Apply JSON edits"):
                try:
                    edited_extraction = _parse_extraction_json(edited_json)
                except ValueError as exc:
                    st.error(f"Invalid JSON: {exc}")
                else:
                    st.session_state["measurement_extraction"] = edited_extraction
                    st.session_state["measurement_extraction_json"] = _extraction_json_text(edited_extraction)
                    st.success("JSON edits applied.")
                    st.rerun()

        measurement_df = _measurements_dataframe(extraction.get("detected_measurements", []))
        opening_state_key = "opening_editor_rows"
        if opening_state_key not in st.session_state:
            st.session_state[opening_state_key] = _openings_dataframe(extraction.get("openings", []))
        if st.button("Add opening row"):
            st.session_state[opening_state_key] = pd.concat(
                [st.session_state[opening_state_key], pd.DataFrame([_blank_opening_row()])],
                ignore_index=True,
            )
            st.rerun()

        st.subheader("Extracted measurements")
        measurement_editor = st.data_editor(
            measurement_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "include": st.column_config.CheckboxColumn("Include"),
                "measurement_type": st.column_config.TextColumn(
                    "Measurement type",
                    help="Examples: roof_area, siding_wall_area, gable_area, ridge_length, eave_length",
                ),
                "shape": st.column_config.TextColumn(
                    "Shape",
                    help="Examples: rectangle, triangle, trapezoid, line, count, unknown",
                ),
                "confidence": st.column_config.NumberColumn("Confidence", min_value=0.0, max_value=1.0, step=0.01),
                "width_ft": st.column_config.NumberColumn("Width ft", min_value=0.0, step=0.1),
                "height_ft": st.column_config.NumberColumn("Height ft", min_value=0.0, step=0.1),
                "base_ft": st.column_config.NumberColumn("Base ft", min_value=0.0, step=0.1),
                "top_width_ft": st.column_config.NumberColumn("Top width ft", min_value=0.0, step=0.1),
                "bottom_width_ft": st.column_config.NumberColumn("Bottom width ft", min_value=0.0, step=0.1),
                "length_ft": st.column_config.NumberColumn("Length ft", min_value=0.0, step=0.1),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=0.1),
                "calculated_area_sqft": st.column_config.NumberColumn("Calculated area sqft", disabled=True),
                "warnings": st.column_config.TextColumn("Warnings", disabled=True),
            },
            disabled=["calculated_area_sqft", "warnings"],
            key="measurement_editor",
        )

        st.subheader("Openings")
        opening_editor = st.data_editor(
            st.session_state[opening_state_key],
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "opening_type": st.column_config.TextColumn(
                    "Opening type",
                    help="Examples: window, door, garage_door, other",
                ),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=1.0),
                "width_ft": st.column_config.NumberColumn("Width ft", min_value=0.0, step=0.1),
                "height_ft": st.column_config.NumberColumn("Height ft", min_value=0.0, step=0.1),
                "confidence": st.column_config.NumberColumn("Confidence", min_value=0.0, max_value=1.0, step=0.01),
            },
            key="opening_editor",
        )

        measurement_rows = _normalize_editor_records(measurement_editor)
        opening_rows = _normalize_editor_records(opening_editor)
        deduct_openings = st.checkbox("Deduct openings from siding wall area", value=trade == "siding")
        preview = _compute_preview(trade, measurement_rows, opening_rows, deduct_openings)

        summary_cols = st.columns(4)
        if trade == "siding":
            summary_cols[0].metric("Wall area", f"{preview['wall_area']:,.2f} sq ft")
            summary_cols[1].metric("Openings", f"{preview['opening_area']:,.2f} sq ft")
            summary_cols[2].metric("Net wall area", f"{preview['net_wall_area']:,.2f} sq ft")
            summary_cols[3].metric("Siding squares", f"{preview['combined_squares']:,.2f}")
        else:
            summary_cols[0].metric("Roof area", f"{preview['roof_area']:,.2f} sq ft")
            summary_cols[1].metric("Roofing squares", f"{preview['combined_squares']:,.2f}")
            summary_cols[2].metric("Linear measurements", str(len(preview["linear_measurements"])))
            summary_cols[3].metric("Image warnings", str(len(preview["warnings"])))

        if preview["warnings"]:
            st.warning("\n".join(f"- {item}" for item in preview["warnings"]))

        st.subheader("Preview")
        preview_df = pd.DataFrame(preview["rows"])
        if preview_df.empty:
            st.info("Select one or more measurements to preview calculated area.")
        else:
            st.dataframe(
                preview_df[
                    [
                        "include",
                        "label",
                        "measurement_type",
                        "shape",
                        "width_ft",
                        "height_ft",
                        "base_ft",
                        "top_width_ft",
                        "bottom_width_ft",
                        "length_ft",
                        "quantity",
                        "confidence",
                        "source_text",
                        "calculated_area_sqft",
                        "warnings",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        approved_by = st.text_input("Approved by")
        if st.button("Save approved measurements"):
            saved = _save_preview_measurements(
                db=db,
                project_id=selected_project.id,
                image_name=image_name,
                trade=trade,
                preview=preview,
                measurement_rows=measurement_rows,
                openings=opening_rows,
                deduct_openings=deduct_openings,
                approved_by=approved_by or None,
            )
            st.success(f"Saved {len(saved)} approved measurement(s).")
            st.caption("Next step: open Quote Builder. Approved measurements for this project are preselected there.")
            st.session_state.pop(opening_state_key, None)
            st.rerun()
finally:
    db.close()
