from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is expected through Streamlit/PyMuPDF installs
    Image = None

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
except ImportError:  # pragma: no cover - optional Streamlit component
    streamlit_image_coordinates = None

from src.auth import require_auth
from src.constants import TAKEOFF_NATIVE_COORDINATE_SPACE, TAKEOFF_REVIEW_COORDINATE_SPACE, TAKEOFF_REVIEW_IMAGE_WIDTH, TAKEOFF_SOURCES
from src.database import SessionLocal, init_db
from src.models import BlueprintFile, BlueprintSheet, Project, TakeoffExtractionRun, TakeoffMeasurement
from src.takeoff_extraction_service import apply_scale_calibration, update_measurement_geometry


def _safe_app_file_path(path_value: str | None, expected_parent: str, blueprint_dir: Path | None = None) -> Path | None:
    if not path_value or blueprint_dir is None:
        return None
    path = Path(path_value).expanduser().resolve()
    blueprint_root = blueprint_dir.expanduser().resolve()
    if not path.exists() or path.parent.name != expected_parent:
        return None
    if not path.is_relative_to(blueprint_root):
        return None
    return path


def _native_points_to_review_display(points: list, image_path: Path | None) -> list[list[float]] | None:
    if not points:
        return []
    if image_path is None or Image is None:
        return None
    try:
        with Image.open(image_path) as image:
            native_width, native_height = image.size
    except Exception:
        return None
    if native_width <= 0 or native_height <= 0:
        return None
    filtered_points = [point for point in points if isinstance(point, (list, tuple)) and len(point) >= 2]
    if native_width == TAKEOFF_REVIEW_IMAGE_WIDTH:
        return [[float(point[0]), float(point[1])] for point in filtered_points]
    scale = TAKEOFF_REVIEW_IMAGE_WIDTH / float(native_width)
    return [[round(float(point[0]) * scale, 4), round(float(point[1]) * scale, 4)] for point in filtered_points]


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
        source = st.selectbox("Source", TAKEOFF_SOURCES)
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

    pending_ai_measurements = (
        db.query(TakeoffMeasurement)
        .filter(
            TakeoffMeasurement.project_id == selected_project.id,
            TakeoffMeasurement.source.in_(["openai_vision_extracted", "manual_overlay_adjusted"]),
            TakeoffMeasurement.approved.is_(False),
        )
        .order_by(TakeoffMeasurement.created_at.desc())
        .all()
    )
    if pending_ai_measurements:
        st.subheader("Pending AI-extracted measurements")
        st.caption("Review, edit, and approve AI takeoff drafts before they can affect Quote Builder.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": item.id,
                        "Trade": item.trade,
                        "Measurement Type": item.measurement_type,
                        "Quantity": item.quantity,
                        "Unit": item.unit,
                        "Confidence": item.confidence_score,
                        "Blueprint File": getattr(item.blueprint_file, "original_file_name", None),
                        "Sheet": getattr(item.blueprint_sheet, "sheet_name", None) or getattr(item.blueprint_sheet, "sheet_type", None),
                        "Notes": item.notes,
                    }
                    for item in pending_ai_measurements
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        review_options = {item.id: item for item in pending_ai_measurements}
        selected_ai_id_key = "selected_ai_takeoff_measurement_id"
        if st.session_state.get(selected_ai_id_key) not in review_options:
            st.session_state[selected_ai_id_key] = pending_ai_measurements[0].id
        selected_ai_measurement_id = st.selectbox(
            "AI draft to review",
            list(review_options),
            key=selected_ai_id_key,
            format_func=lambda measurement_id: (
                f"#{measurement_id} - {review_options[measurement_id].measurement_type} "
                f"({review_options[measurement_id].quantity:g} {review_options[measurement_id].unit})"
            ),
        )
        selected_ai_measurement = review_options[selected_ai_measurement_id]

        with st.expander("Interactive overlay / scale calibration", expanded=True):
            sheet = selected_ai_measurement.blueprint_sheet
            latest_run = None
            if sheet is not None:
                run_query = db.query(TakeoffExtractionRun).filter(TakeoffExtractionRun.blueprint_sheet_id == sheet.id)
                if selected_ai_measurement.created_at is not None:
                    run_query = run_query.filter(TakeoffExtractionRun.created_at <= selected_ai_measurement.created_at)
                latest_run = run_query.order_by(TakeoffExtractionRun.created_at.desc()).first()
                if latest_run is None:
                    latest_run = (
                        db.query(TakeoffExtractionRun)
                        .filter(TakeoffExtractionRun.blueprint_sheet_id == sheet.id)
                        .order_by(TakeoffExtractionRun.created_at.desc())
                        .first()
                    )
            blueprint_dir = Path(sheet.blueprint_file.file_path).expanduser().resolve().parent if sheet is not None and sheet.blueprint_file is not None else None
            image_path = _safe_app_file_path(getattr(latest_run, "rendered_image_path", None), "blueprint_renders", blueprint_dir)
            overlay_path = _safe_app_file_path(getattr(latest_run, "overlay_path", None), "blueprint_overlays", blueprint_dir)
            clicked_point = None
            if image_path:
                if streamlit_image_coordinates is not None:
                    clicked_point = streamlit_image_coordinates(
                        str(image_path),
                        width=TAKEOFF_REVIEW_IMAGE_WIDTH,
                        key=f"overlay_click_{selected_ai_measurement.id}",
                    )
                    st.caption(
                        f"Click points on the fixed {TAKEOFF_REVIEW_IMAGE_WIDTH}px-wide review image above, "
                        "or edit the point table manually. Calibrations and clicked points use this same review-display coordinate space."
                    )
                    if clicked_point:
                        st.caption(f"Last clicked pixel: x={clicked_point['x']}, y={clicked_point['y']}")
                else:
                    st.image(str(image_path), caption="Rendered blueprint sheet. Install streamlit-image-coordinates to click points directly; manual point editing still works.", width=TAKEOFF_REVIEW_IMAGE_WIDTH)
                if overlay_path:
                    st.image(str(overlay_path), caption="AI overlay reference", width=TAKEOFF_REVIEW_IMAGE_WIDTH)
            else:
                st.info("No rendered sheet image found yet. Run automatic takeoff from the Blueprints page first.")

            if sheet is not None:
                st.caption(f"Current sheet calibration: {sheet.calibrated_scale or sheet.scale_text or 'Not calibrated'}")
                with st.form(f"scale_calibration_{selected_ai_measurement.id}"):
                    col_px, col_ft = st.columns(2)
                    with col_px:
                        pixel_distance = st.number_input("Known line length in review-display pixels", min_value=0.0, value=0.0, step=1.0)
                    with col_ft:
                        real_distance_ft = st.number_input("Known real length in feet", min_value=0.0, value=0.0, step=1.0)
                    calibrated_by = st.text_input("Calibrated by")
                    if st.form_submit_button("Save scale calibration"):
                        try:
                            result = apply_scale_calibration(db, sheet.id, pixel_distance, real_distance_ft, calibrated_by or None)
                            st.success(f"Saved calibration: {result['label']}")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

            st.caption("Edit geometry points. Use pixels for clicked review-image points, or feet for manually entered real-world dimensions.")
            geometry_edits = list(getattr(selected_ai_measurement, "geometry_edits", []) or [])
            latest_geometry = {}
            if geometry_edits:
                latest_geometry = max(geometry_edits, key=lambda edit: (edit.created_at, edit.id or 0)).geometry_json or {}
            point_state_key = f"geometry_clicked_points_{selected_ai_measurement.id}"
            units_key = f"geometry_units_{selected_ai_measurement.id}"
            editor_version_key = f"geometry_points_version_{selected_ai_measurement.id}"
            if point_state_key not in st.session_state:
                st.session_state[point_state_key] = []
            if editor_version_key not in st.session_state:
                st.session_state[editor_version_key] = 0
            if clicked_point:
                point = {"x": float(clicked_point["x"]), "y": float(clicked_point["y"])}
                if not st.session_state[point_state_key] or st.session_state[point_state_key][-1] != point:
                    st.session_state[point_state_key].append(point)
                    st.session_state[editor_version_key] += 1
                st.session_state[units_key] = "pixels"
            if units_key not in st.session_state and latest_geometry.get("points_px"):
                st.session_state[units_key] = "pixels"
            geometry_units = st.radio("Point units", ["feet", "pixels"], horizontal=True, key=units_key)
            shape_options = ["polygon", "traced_polygon", "polyline", "traced_line", "line", "count"]
            if geometry_units == "feet":
                shape_options.insert(5, "rectangle")
            initial_shape = latest_geometry.get("shape") if latest_geometry.get("shape") in shape_options else None
            edit_shape = st.selectbox(
                "Geometry shape",
                shape_options,
                index=shape_options.index(initial_shape) if initial_shape in shape_options else 0,
                key=f"geometry_shape_{selected_ai_measurement.id}",
            )
            initial_points = latest_geometry.get("points_px" if geometry_units == "pixels" else "points_ft") or []
            if geometry_units == "pixels" and latest_geometry.get("point_coordinate_space") == TAKEOFF_NATIVE_COORDINATE_SPACE:
                converted_points = _native_points_to_review_display(initial_points, image_path)
                if converted_points is None:
                    initial_points = []
                    st.warning("Existing AI points were captured in native image pixels, but the rendered image could not be opened to convert them into review-display pixels. Click new points or enter feet-based geometry before saving.")
                else:
                    initial_points = converted_points
            if not initial_points and geometry_units == "feet" and edit_shape == "rectangle" and latest_geometry.get("width_ft") and latest_geometry.get("height_ft"):
                initial_points = [[0.0, 0.0], [float(latest_geometry["width_ft"]), float(latest_geometry["height_ft"])]]
            initial_point_rows = [{"x": float(point[0]), "y": float(point[1])} for point in initial_points if isinstance(point, (list, tuple)) and len(point) >= 2]
            clicked_point_rows = list(st.session_state[point_state_key])
            default_rows = [] if edit_shape == "count" else initial_point_rows + clicked_point_rows or [{"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 0.0}]
            default_points = pd.DataFrame(default_rows, columns=["x", "y"])
            edited_points = st.data_editor(
                default_points,
                num_rows="dynamic",
                use_container_width=True,
                key=f"geometry_points_{selected_ai_measurement.id}_{st.session_state[editor_version_key]}",
            )
            count_quantity = int(latest_geometry.get("quantity") or selected_ai_measurement.quantity or 0) if edit_shape == "count" else 0
            if edit_shape == "count":
                count_quantity = st.number_input("Count quantity", min_value=0, value=count_quantity, step=1, key=f"geometry_count_{selected_ai_measurement.id}")
            openings_default = json.dumps(latest_geometry.get("openings") or [], indent=2)
            openings_json = st.text_area("Opening deductions JSON", value=openings_default, key=f"geometry_openings_{selected_ai_measurement.id}")
            geometry_notes = st.text_area("Geometry edit notes", value="Adjusted in overlay reviewer.", key=f"geometry_notes_{selected_ai_measurement.id}")
            geometry_editor = st.text_input("Geometry edited by", key=f"geometry_editor_{selected_ai_measurement.id}")
            if st.button("Recalculate and save geometry", key=f"save_geometry_{selected_ai_measurement.id}"):
                try:
                    points = []
                    for _, row in edited_points.dropna(how="all").iterrows():
                        try:
                            points.append([float(row["x"]), float(row["y"])])
                        except (TypeError, ValueError):
                            continue
                    openings = json.loads(openings_json or "[]")
                    if not isinstance(openings, list):
                        raise ValueError("Opening deductions JSON must be a list.")
                    geometry = {"shape": edit_shape, "deduct_openings": bool(openings), "openings": openings}
                    if edit_shape in {"polygon", "traced_polygon", "polyline", "traced_line", "line"}:
                        geometry["points_px" if geometry_units == "pixels" else "points_ft"] = points
                        if geometry_units == "pixels":
                            geometry["point_coordinate_space"] = TAKEOFF_REVIEW_COORDINATE_SPACE
                    elif edit_shape == "rectangle" and len(points) >= 2:
                        width = abs(points[1][0] - points[0][0])
                        height = abs(points[1][1] - points[0][1])
                        if geometry_units == "pixels":
                            st.error("Rectangle pixel editing is not supported yet; use polygon/polyline pixels or enter rectangle dimensions in feet.")
                            st.stop()
                        geometry.update({"width_ft": width, "height_ft": height})
                    elif edit_shape == "count":
                        if int(count_quantity) <= 0:
                            raise ValueError("Count geometry requires a positive count quantity.")
                        geometry["quantity"] = int(count_quantity)
                    updated = update_measurement_geometry(
                        db,
                        selected_ai_measurement.id,
                        geometry=geometry,
                        edited_by=geometry_editor or None,
                        notes=geometry_notes,
                    )
                    st.session_state[point_state_key] = []
                    st.session_state[editor_version_key] += 1
                    st.success(f"Updated draft measurement to {updated.quantity:g} {updated.unit}. Review/approve it below when ready.")
                    st.rerun()
                except (ValueError, json.JSONDecodeError, TypeError) as exc:
                    st.error(f"Could not save geometry edit: {exc}")

        with st.form("review_ai_takeoff_measurement"):
            ai_trade = st.selectbox("Trade", ["roofing", "siding"], index=["roofing", "siding"].index(selected_ai_measurement.trade) if selected_ai_measurement.trade in {"roofing", "siding"} else 0)
            ai_measurement_type = st.text_input("Measurement type", value=selected_ai_measurement.measurement_type)
            ai_quantity = st.number_input("Quantity", min_value=0.0, value=float(selected_ai_measurement.quantity or 0), step=1.0)
            ai_unit_options = ["square", "square_foot", "linear_foot", "each", "job", "allowance"]
            ai_unit = st.selectbox(
                "Unit",
                ai_unit_options,
                index=ai_unit_options.index(selected_ai_measurement.unit) if selected_ai_measurement.unit in ai_unit_options else 1,
            )
            ai_confidence = st.number_input("Confidence score", min_value=0.0, max_value=1.0, value=float(selected_ai_measurement.confidence_score or 0), step=0.05)
            approve_ai = st.checkbox("Approve this measurement", value=False)
            ai_approved_by = st.text_input("Approved by", value=selected_ai_measurement.approved_by or "")
            ai_notes = st.text_area("Review notes", value=selected_ai_measurement.notes or "")
            review_submitted = st.form_submit_button("Save AI measurement review")
            if review_submitted and ai_measurement_type:
                selected_ai_measurement.trade = ai_trade
                selected_ai_measurement.measurement_type = ai_measurement_type
                selected_ai_measurement.quantity = ai_quantity
                selected_ai_measurement.unit = ai_unit
                selected_ai_measurement.confidence_score = ai_confidence
                selected_ai_measurement.notes = ai_notes
                selected_ai_measurement.approved = approve_ai
                selected_ai_measurement.approved_by = ai_approved_by or None if approve_ai else None
                db.commit()
                st.success("AI measurement review saved.")
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
