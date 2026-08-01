from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.constants import OPENAI_VISION_MODEL_DEFAULT

try:  # pragma: no cover - dependency is installed in production/test envs
    from openai import OpenAI
except Exception:  # pragma: no cover - keeps importable without the SDK installed
    OpenAI = None


class DetectedMeasurement(BaseModel):
    label: str
    measurement_type: str
    shape: Literal["rectangle", "triangle", "trapezoid", "polygon", "traced_polygon", "line", "polyline", "traced_line", "count", "unknown"]
    width_ft: float | None = None
    height_ft: float | None = None
    base_ft: float | None = None
    top_width_ft: float | None = None
    bottom_width_ft: float | None = None
    length_ft: float | None = None
    segments_ft: list[float] | None = None
    points_ft: list[list[float]] | None = None
    quantity: float | None = None
    deduct_openings: bool = False
    openings: list["OpeningMeasurement"] | None = None
    overlay_points: list[list[float]] | None = None
    confidence: float = Field(ge=0, le=1)
    source_text: str | None = None
    scale_calibration: str | None = None


class OpeningMeasurement(BaseModel):
    opening_type: Literal["window", "door", "garage_door", "other"]
    label: str | None = None
    parent_label: str | None = None
    quantity: float | None = None
    width_ft: float | None = None
    height_ft: float | None = None
    confidence: float = Field(ge=0, le=1)


class VisionExtractionResponse(BaseModel):
    trade: Literal["roofing", "siding", "unknown"]
    detected_measurements: list[DetectedMeasurement]
    openings: list[OpeningMeasurement]
    calculation_recommendations: list[str]
    warnings: list[str]
    confidence: float = Field(ge=0, le=1)


def image_to_base64_data_url(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower().lstrip(".")
    mime_type_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    mime_type = mime_type_map.get(suffix)
    if mime_type is None:
        raise ValueError(f"Unsupported image type: {path.suffix or suffix}")
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _build_instructions(trade_hint: str | None = None) -> str:
    trade_text = f"Trade hint: {trade_hint}." if trade_hint else "Trade hint: unknown."
    return (
        "Extract construction measurements visible in the uploaded image. "
        "Focus only on roofing and siding. Read typed or handwritten measurements if visible. "
        "Prefer printed dimensions and sheet scale/calibration text; do not infer a scale from pixels unless a visible scale or calibration line is present. "
        "Return polygon/traced_polygon points_ft for traced area shapes and line/polyline segments_ft or length_ft for trim, ridge, rake, and eave runs. "
        "For siding walls, include opening deductions only when window/door dimensions are visible and set deduct_openings true with opening dimensions. "
        "If overlay geometry is visible, include overlay_points as image pixel points so the app can render review overlays. "
        "Do not guess missing dimensions. If a dimension is unclear, return null and add a warning. "
        "If units are not visible, assume feet only if strongly implied; otherwise return null and add a warning. "
        "Do not calculate final quote price. Do not create material pricing. Do not estimate labor. "
        "Return structured JSON only. "
        f"{trade_text}"
    )


def _coerce_response(response) -> dict:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        if hasattr(parsed, "model_dump"):
            return parsed.model_dump()
        if isinstance(parsed, dict):
            return parsed
    output_text = getattr(response, "output_text", None)
    if output_text:
        if isinstance(output_text, str):
            return VisionExtractionResponse.model_validate_json(output_text).model_dump()
        return VisionExtractionResponse.model_validate_json(str(output_text)).model_dump()
    raise RuntimeError("OpenAI vision response did not include parsed JSON output.")


def parse_measurement_response(response) -> dict:
    return _coerce_response(response)


def extract_measurements_from_image(image_path: str, trade_hint: str | None = None) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set in the environment before using image measurement extraction.")
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed. Add openai>=2.0.0 to the environment.")

    model = os.getenv("OPENAI_VISION_MODEL", OPENAI_VISION_MODEL_DEFAULT)
    data_url = image_to_base64_data_url(image_path)
    client = OpenAI(api_key=api_key)
    instructions = _build_instructions(trade_hint)

    try:
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": instructions},
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ],
                }
            ],
            text_format=VisionExtractionResponse,
        )
    except Exception as exc:  # pragma: no cover - network/API failure path
        raise RuntimeError(f"OpenAI vision extraction failed: {exc}") from exc

    try:
        return parse_measurement_response(response)
    except Exception as exc:  # pragma: no cover - defensive parsing path
        raise RuntimeError(f"OpenAI vision extraction returned an unreadable response: {exc}") from exc
