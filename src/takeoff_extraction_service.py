from __future__ import annotations

import html
from pathlib import Path
from typing import Callable

from src.blueprint_service import render_pdf_sheet_to_image
from src.measurement_calculator import calculate_area_from_measurement, calculate_total_opening_area
from src.models import BlueprintSheet, QuoteMeasurementLink, TakeoffExtractionRun, TakeoffMeasurement
from src.openai_vision_service import extract_measurements_from_image

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


def _item_openings(item: dict, extraction: dict) -> list[dict]:
    openings = item.get("openings")
    if openings is not None:
        return openings if isinstance(openings, list) else []
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


def _write_overlay_svg(items: list[dict], overlay_dir: str, sheet_id: int) -> str | None:
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
    svg = "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200">',
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
        overlay_path = _write_overlay_svg(detected_items, overlay_output_dir, sheet.id)
        for item in extraction.get("detected_measurements", []):
            if not isinstance(item, dict):
                skipped.append({"item": item, "reason": "Measurement result was not an object."})
                continue
            quantity, unit, quantity_warnings = _quantity_from_detected_measurement(item, extraction)
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
