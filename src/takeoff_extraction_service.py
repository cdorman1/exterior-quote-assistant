from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Callable

from src.blueprint_service import render_pdf_sheet_to_image
from src.constants import TAKEOFF_NATIVE_COORDINATE_SPACE, TAKEOFF_REVIEW_COORDINATE_SPACE
from src.measurement_calculator import calculate_area_from_measurement, calculate_total_opening_area
from src.models import (
    BlueprintScaleCalibrationEdit,
    BlueprintSheet,
    QuoteMeasurementLink,
    TakeoffExtractionRun,
    TakeoffMeasurement,
    TakeoffMeasurementGeometryEdit,
)
from src.openai_vision_service import extract_measurements_from_image

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Streamlit/PyMuPDF deployments generally include Pillow
    Image = None

ExtractionCallable = Callable[[str, str | None], dict]


def _polygon_area(points: list[list[float]] | list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        total += float(point[0]) * float(next_point[1])
        total -= float(next_point[0]) * float(point[1])
    return abs(total) / 2


def _polyline_length(item: dict) -> float | None:
    if item.get("segments_ft"):
        return sum(float(segment) for segment in item["segments_ft"])
    points = item.get("points_ft") or []
    if len(points) < 2:
        return None
    length = 0.0
    for point, next_point in zip(points, points[1:]):
        dx = float(next_point[0]) - float(point[0])
        dy = float(next_point[1]) - float(point[1])
        length += (dx**2 + dy**2) ** 0.5
    return length


def _missing(value) -> bool:
    return value is None or value == ""


def _item_openings(item: dict, extraction: dict):
    openings = item.get("openings")
    if openings is not None:
        return openings
    label = item.get("label")
    global_openings = extraction.get("openings") or []
    if not label:
        return global_openings if isinstance(global_openings, list) else []
    matched = [opening for opening in global_openings if isinstance(opening, dict) and opening.get("parent_label") == label]
    return matched


def _quantity_from_detected_measurement(item: dict, extraction: dict) -> tuple[float | None, str | None, list[str]]:
    shape = str(item.get("shape") or "unknown").lower()
    warnings: list[str] = []

    if shape in {"rectangle", "triangle", "trapezoid"}:
        area_result = calculate_area_from_measurement(item)
        warnings.extend(area_result.get("warnings") or [])
        area_sqft = area_result.get("area_sqft")
        if area_sqft is None:
            return None, None, warnings
        opening_area = 0.0
        if item.get("deduct_openings"):
            opening_area = calculate_total_opening_area(_item_openings(item, extraction))
            area_sqft = max(float(area_sqft) - opening_area, 0)
            warnings.append(f"Opening deductions: {opening_area:g} sq ft.")
        return round(float(area_sqft), 2), "square_foot", warnings

    if shape in {"polygon", "traced_polygon"}:
        points = item.get("points_ft") or item.get("vertices_ft") or []
        if len(points) < 3:
            warnings.append("Polygon measurements require at least three points_ft.")
            return None, None, warnings
        area_sqft = _polygon_area(points)
        if item.get("deduct_openings"):
            opening_area = calculate_total_opening_area(_item_openings(item, extraction))
            area_sqft = max(float(area_sqft) - opening_area, 0)
            warnings.append(f"Opening deductions: {opening_area:g} sq ft.")
        return round(float(area_sqft), 2), "square_foot", warnings

    if shape in {"line", "polyline", "traced_line"}:
        length = item.get("length_ft") or item.get("quantity") or _polyline_length(item)
        if length is None:
            warnings.append("Line measurements require length_ft, segments_ft, points_ft, or quantity.")
            return None, None, warnings
        return round(float(length), 2), "linear_foot", warnings

    if shape == "count":
        quantity = item.get("quantity")
        if quantity is None:
            warnings.append("Count measurements require quantity.")
            return None, None, warnings
        return round(float(quantity), 2), "each", warnings

    quantity = item.get("quantity")
    if quantity is not None:
        return round(float(quantity), 2), "each", warnings

    warnings.append(f"Unsupported measurement shape: {shape}.")
    return None, None, warnings


def _build_measurement_notes(item: dict, extraction: dict, warnings: list[str]) -> str:
    notes: list[str] = []
    label = item.get("label")
    if label:
        notes.append(f"AI label: {label}")
    source_text = item.get("source_text")
    if source_text:
        notes.append(f"Source text: {source_text}")
    if item.get("scale_calibration"):
        notes.append(f"Scale calibration: {item['scale_calibration']}")
    if extraction.get("_sheet_scale_text"):
        notes.append(f"Plan scale text: {extraction['_sheet_scale_text']}")
    all_warnings = [str(warning) for warning in (extraction.get("warnings") or []) + warnings if warning]
    if all_warnings:
        notes.append("Warnings: " + "; ".join(all_warnings))
    recommendations = [str(item) for item in extraction.get("calculation_recommendations", []) if item]
    if recommendations:
        notes.append("Recommendations: " + "; ".join(recommendations))
    return "\n".join(notes)


def _overlay_points_for_item(item: dict) -> list[list[float]]:
    points = item.get("overlay_points") or item.get("points_px") or item.get("polygon_px") or []
    if isinstance(points, list) and all(isinstance(point, (list, tuple)) and len(point) >= 2 for point in points):
        return [[float(point[0]), float(point[1])] for point in points]
    return []


def _geometry_from_detected_item(item: dict) -> dict:
    keys = [
        "shape",
        "points_ft",
        "vertices_ft",
        "points_px",
        "polygon_px",
        "overlay_points",
        "width_ft",
        "height_ft",
        "length_ft",
        "segments_ft",
        "quantity",
        "deduct_openings",
        "openings",
        "label",
    ]
    geometry = {key: item[key] for key in keys if key in item}
    overlay_points = _overlay_points_for_item(item)
    if overlay_points:
        geometry.setdefault("points_px", overlay_points)
        geometry.setdefault("point_coordinate_space", TAKEOFF_NATIVE_COORDINATE_SPACE)
    geometry.setdefault("shape", item.get("shape") or "unknown")
    return geometry


def _write_overlay_svg(items: list[dict], overlay_dir: str, sheet_id: int, image_path: str | None = None) -> str | None:
    shapes: list[str] = []
    for item in items:
        points = _overlay_points_for_item(item)
        if not points:
            continue
        label = html.escape(str(item.get("label") or item.get("measurement_type") or "measurement"))
        color = "#22c55e" if str(item.get("shape", "")).lower() in {"rectangle", "polygon", "traced_polygon"} else "#38bdf8"
        point_text = " ".join(f"{x:g},{y:g}" for x, y in points)
        if len(points) >= 3:
            shapes.append(f'<polygon points="{point_text}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="3" />')
        else:
            shapes.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="3" />')
        shapes.append(f'<text x="{points[0][0]:g}" y="{points[0][1] - 6:g}" fill="{color}" font-size="16">{label}</text>')
    if not shapes:
        return None
    target_dir = Path(overlay_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"sheet_{sheet_id}_takeoff_overlay.svg"
    width, height = 1600, 1200
    if image_path and Image is not None:
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            width, height = 1600, 1200
    svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#0f172a" fill-opacity="0.04" />',
            *shapes,
            "</svg>",
        ]
    )
    path.write_text(svg, encoding="utf-8")
    return str(path)


def _default_render_dir(file_path: str) -> str:
    resolved = Path(file_path).resolve()
    return str(resolved.parent / "blueprint_renders")


def run_auto_takeoff(
    session,
    blueprint_sheet_id: int,
    trade_hint: str,
    render_dir: str | None = None,
    overlay_dir: str | None = None,
    extractor: ExtractionCallable = extract_measurements_from_image,
) -> dict:
    sheet = session.get(BlueprintSheet, blueprint_sheet_id)
    if sheet is None:
        raise ValueError(f"Blueprint sheet {blueprint_sheet_id} was not found.")
    blueprint_file = sheet.blueprint_file
    if blueprint_file is None:
        raise ValueError(f"Blueprint sheet {blueprint_sheet_id} is not attached to a blueprint file.")

    output_dir = render_dir or _default_render_dir(blueprint_file.file_path)
    image_path = render_pdf_sheet_to_image(
        blueprint_file.file_path,
        page_number=sheet.page_number,
        output_dir=output_dir,
    )
    extraction_run = TakeoffExtractionRun(
        project_id=blueprint_file.project_id,
        blueprint_file_id=blueprint_file.id,
        blueprint_sheet_id=sheet.id,
        trade=trade_hint,
        status="started",
        rendered_image_path=image_path,
    )
    session.add(extraction_run)
    session.flush()

    created: list[TakeoffMeasurement] = []
    skipped: list[dict] = []
    extraction: dict = {}
    overlay_path: str | None = None
    try:
        extraction = extractor(image_path, trade_hint)
        if sheet.scale_text and isinstance(extraction, dict):
            extraction.setdefault("_sheet_scale_text", sheet.scale_text)
        detected_items = [item for item in extraction.get("detected_measurements", []) if isinstance(item, dict)]
        overlay_output_dir = overlay_dir or str(Path(blueprint_file.file_path).resolve().parent / "blueprint_overlays")
        overlay_path = _write_overlay_svg(detected_items, overlay_output_dir, sheet.id, image_path=image_path)
        for item in extraction.get("detected_measurements", []):
            if not isinstance(item, dict):
                skipped.append({"item": item, "reason": "Measurement result was not an object."})
                continue
            try:
                if item.get("deduct_openings"):
                    _validate_openings(_item_openings(item, extraction))
            except (TypeError, ValueError) as exc:
                skipped.append({"item": item, "reason": str(exc)})
                continue
            try:
                quantity, unit, quantity_warnings = _quantity_from_detected_measurement(item, extraction)
            except (TypeError, ValueError, OverflowError) as exc:
                skipped.append({"item": item, "reason": f"Quantity calculation failed: {exc}"})
                continue
            measurement_type = str(item.get("measurement_type") or "general_measurement").strip() or "general_measurement"
            if quantity is None or unit is None:
                skipped.append({"item": item, "reason": "; ".join(quantity_warnings) or "Quantity could not be calculated."})
                continue
            measurement = TakeoffMeasurement(
                project_id=blueprint_file.project_id,
                blueprint_file_id=blueprint_file.id,
                blueprint_sheet_id=sheet.id,
                trade=str(extraction.get("trade") or trade_hint or "unknown"),
                measurement_type=measurement_type,
                quantity=quantity,
                unit=unit,
                source="openai_vision_extracted",
                confidence_score=float(item.get("confidence") or extraction.get("confidence") or 0),
                approved=False,
                notes=_build_measurement_notes(item, extraction, quantity_warnings),
            )
            session.add(measurement)
            session.flush()
            session.add(
                TakeoffMeasurementGeometryEdit(
                    takeoff_measurement_id=measurement.id,
                    blueprint_sheet_id=sheet.id,
                    edited_by="AI extraction",
                    geometry_json=_geometry_from_detected_item(item),
                    scale_json={"label": sheet.calibrated_scale or sheet.scale_text} if (sheet.calibrated_scale or sheet.scale_text) else None,
                    previous_quantity=None,
                    updated_quantity=quantity,
                    previous_unit=None,
                    updated_unit=unit,
                    notes="Initial AI-detected geometry for overlay reviewer.",
                )
            )
            created.append(measurement)

        extraction_run.status = "completed"
        extraction_run.raw_response = extraction
        extraction_run.warnings_json = extraction.get("warnings", [])
        extraction_run.created_measurement_count = len(created)
        extraction_run.skipped_measurement_count = len(skipped)
        extraction_run.overlay_path = overlay_path
        session.commit()
    except Exception as exc:
        extraction_run.status = "failed"
        extraction_run.error_message = str(exc)
        session.commit()
        raise

    return {
        "run_id": extraction_run.id,
        "image_path": image_path,
        "overlay_path": overlay_path,
        "created_count": len(created),
        "created_measurement_ids": [item.id for item in created],
        "skipped_count": len(skipped),
        "skipped": skipped,
        "warnings": extraction.get("warnings", []),
        "recommendations": extraction.get("calculation_recommendations", []),
        "confidence": extraction.get("confidence"),
    }


def _calibrated_scale_json(sheet: BlueprintSheet | None) -> dict | None:
    if sheet is None:
        return None
    latest_edit = None
    if getattr(sheet, "scale_calibration_edits", None):
        latest_edit = max(sheet.scale_calibration_edits, key=lambda edit: (edit.created_at, edit.id or 0))
    if latest_edit is not None:
        return {
            "feet_per_pixel": latest_edit.feet_per_pixel,
            "label": latest_edit.label,
            "calibration_edit_id": latest_edit.id,
            "coordinate_space": TAKEOFF_REVIEW_COORDINATE_SPACE,
        }
    if not sheet.calibrated_scale:
        return None
    if " ft/review px" not in sheet.calibrated_scale:
        return {"label": sheet.calibrated_scale}
    parts = sheet.calibrated_scale.split(" ft/review px", 1)
    try:
        feet_per_pixel = float(parts[0])
    except (TypeError, ValueError):
        return {"label": sheet.calibrated_scale}
    return {"feet_per_pixel": feet_per_pixel, "label": sheet.calibrated_scale, "coordinate_space": TAKEOFF_REVIEW_COORDINATE_SPACE}


def _convert_points_px_to_ft(points_px: list, feet_per_pixel: float) -> list[list[float]]:
    return [[round(float(point[0]) * feet_per_pixel, 4), round(float(point[1]) * feet_per_pixel, 4)] for point in points_px]


def _geometry_with_calibrated_points(geometry: dict, scale_json: dict | None) -> dict:
    normalized = dict(geometry)
    feet_per_pixel = (scale_json or {}).get("feet_per_pixel")
    points_px = normalized.get("points_px")
    if feet_per_pixel and points_px and not normalized.get("points_ft"):
        normalized["points_ft"] = _convert_points_px_to_ft(points_px, float(feet_per_pixel))
    return normalized


def _validate_finite_points(points: list, field_name: str) -> None:
    if not isinstance(points, list):
        raise ValueError(f"Invalid {field_name}: expected a list of points.")
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(f"Invalid {field_name}: each point needs x and y values.")
        for value in point[:2]:
            if not math.isfinite(float(value)):
                raise ValueError(f"Invalid {field_name}: point coordinates must be finite numbers.")


def _validate_openings(openings: list | None) -> None:
    if openings in (None, []):
        return
    if not isinstance(openings, list):
        raise ValueError("Invalid openings: expected a JSON list.")
    for opening in openings:
        if not isinstance(opening, dict):
            raise ValueError("Invalid openings: each opening must be an object.")
        try:
            quantity_value = opening["quantity"] if opening.get("quantity") is not None else 1
            quantity = 1.0 if _missing(quantity_value) else float(quantity_value)
            width = float(opening.get("width_ft", 0) or 0)
            height = float(opening.get("height_ft", 0) or 0)
            area = float(opening.get("area_sqft", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("Opening dimensions must be numeric values.") from exc
        if not all(math.isfinite(value) for value in [quantity, width, height, area]):
            raise ValueError("Opening dimensions must be finite numbers.")
        if quantity <= 0:
            raise ValueError("Opening quantity must be positive.")
        if area < 0 or width < 0 or height < 0:
            raise ValueError("Opening dimensions must be positive values.")
        if area == 0 and (width == 0 or height == 0):
            raise ValueError("Opening needs area_sqft or positive width_ft and height_ft.")


def _validate_geometry(geometry: dict, scale_json: dict | None) -> None:
    shape = str(geometry.get("shape") or "unknown").lower()
    if geometry.get("deduct_openings"):
        _validate_openings(geometry.get("openings"))
    if geometry.get("points_ft"):
        _validate_finite_points(geometry["points_ft"], "points_ft")
    if geometry.get("points_px"):
        _validate_finite_points(geometry["points_px"], "points_px")
        if not (scale_json or {}).get("feet_per_pixel"):
            raise ValueError("Pixel geometry requires a saved scale calibration.")
        if geometry.get("point_coordinate_space") != (scale_json or {}).get("coordinate_space"):
            raise ValueError("Pixel geometry coordinate space must match the saved scale calibration.")
    if shape in {"polygon", "traced_polygon"} and len(geometry.get("points_ft") or []) < 3:
        raise ValueError("Polygon geometry requires at least three finite points.")
    if shape in {"line", "polyline", "traced_line"} and not geometry.get("length_ft") and len(geometry.get("points_ft") or []) < 2:
        raise ValueError("Line geometry requires at least two finite points or length_ft.")
    if shape == "rectangle":
        width = float(geometry.get("width_ft", 0) or 0)
        height = float(geometry.get("height_ft", 0) or 0)
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            raise ValueError("Rectangle geometry requires finite positive width_ft and height_ft.")


def apply_scale_calibration(
    session,
    blueprint_sheet_id: int,
    pixel_distance: float,
    real_distance_ft: float,
    calibrated_by: str | None = None,
) -> dict:
    try:
        pixel_distance_float = float(pixel_distance)
        real_distance_float = float(real_distance_ft)
    except (TypeError, ValueError) as exc:
        raise ValueError("Scale calibration distances must be numeric values.") from exc
    if not math.isfinite(pixel_distance_float) or pixel_distance_float <= 0:
        raise ValueError("Pixel distance must be a finite value greater than zero.")
    if not math.isfinite(real_distance_float) or real_distance_float <= 0:
        raise ValueError("Real distance must be a finite value greater than zero.")
    sheet = session.get(BlueprintSheet, blueprint_sheet_id)
    if sheet is None:
        raise ValueError(f"Blueprint sheet {blueprint_sheet_id} was not found.")
    feet_per_pixel = real_distance_float / pixel_distance_float
    previous_calibrated_scale = sheet.calibrated_scale
    sheet.calibrated_scale = f"{feet_per_pixel:g} ft/review px ({pixel_distance_float:g} review px = {real_distance_float:g} ft)"
    session.add(
        BlueprintScaleCalibrationEdit(
            blueprint_sheet_id=sheet.id,
            calibrated_by=calibrated_by,
            pixel_distance=pixel_distance_float,
            real_distance_ft=real_distance_float,
            feet_per_pixel=feet_per_pixel,
            label=sheet.calibrated_scale,
            previous_calibrated_scale=previous_calibrated_scale,
        )
    )
    session.commit()
    return {
        "blueprint_sheet_id": sheet.id,
        "feet_per_pixel": feet_per_pixel,
        "pixel_distance": pixel_distance_float,
        "real_distance_ft": real_distance_float,
        "calibrated_by": calibrated_by,
        "label": sheet.calibrated_scale,
    }


def update_measurement_geometry(
    session,
    takeoff_measurement_id: int,
    geometry: dict,
    edited_by: str | None = None,
    notes: str | None = None,
) -> TakeoffMeasurement:
    measurement = session.get(TakeoffMeasurement, takeoff_measurement_id)
    if measurement is None:
        raise ValueError(f"Takeoff measurement {takeoff_measurement_id} was not found.")
    scale_json = _calibrated_scale_json(measurement.blueprint_sheet)
    normalized_geometry = _geometry_with_calibrated_points(geometry, scale_json)
    _validate_geometry(normalized_geometry, scale_json)
    quantity, unit, warnings = _quantity_from_detected_measurement(normalized_geometry, {"warnings": []})
    if quantity is None or unit is None:
        raise ValueError("Geometry could not be converted into a measurement quantity: " + "; ".join(warnings))
    if not math.isfinite(float(quantity)) or float(quantity) <= 0:
        raise ValueError("Geometry must produce a finite positive quantity.")

    previous_quantity = measurement.quantity
    previous_unit = measurement.unit
    existing_notes = measurement.notes or ""
    review_notes = notes or "Geometry adjusted in overlay reviewer."
    warning_text = f"\nGeometry warnings: {'; '.join(warnings)}" if warnings else ""
    measurement.quantity = quantity
    measurement.unit = unit
    measurement.source = "manual_overlay_adjusted"
    measurement.approved = False
    measurement.approved_by = None
    measurement.notes = (existing_notes + "\n" if existing_notes else "") + review_notes + warning_text
    session.add(
        TakeoffMeasurementGeometryEdit(
            takeoff_measurement_id=measurement.id,
            blueprint_sheet_id=measurement.blueprint_sheet_id,
            edited_by=edited_by,
            geometry_json=normalized_geometry,
            scale_json=scale_json,
            previous_quantity=previous_quantity,
            updated_quantity=quantity,
            previous_unit=previous_unit,
            updated_unit=unit,
            notes=notes,
        )
    )
    session.commit()
    session.refresh(measurement)
    return measurement


def link_quote_measurements(session, quote_id: int, takeoff_measurement_ids: list[int], usage: str = "material_quantity") -> int:
    existing_ids = {
        row.takeoff_measurement_id
        for row in session.query(QuoteMeasurementLink)
        .filter(
            QuoteMeasurementLink.quote_id == quote_id,
            QuoteMeasurementLink.takeoff_measurement_id.in_(takeoff_measurement_ids),
            QuoteMeasurementLink.usage == usage,
        )
        .all()
    }
    created_count = 0
    for measurement_id in takeoff_measurement_ids:
        if measurement_id in existing_ids:
            continue
        session.add(
            QuoteMeasurementLink(
                quote_id=quote_id,
                takeoff_measurement_id=measurement_id,
                usage=usage,
            )
        )
        created_count += 1
    session.commit()
    return created_count
