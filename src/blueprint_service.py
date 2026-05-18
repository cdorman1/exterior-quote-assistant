from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

try:
    import fitz
except ImportError:  # pragma: no cover - dependency is added in requirements
    fitz = None

from src.models import BlueprintFile, BlueprintSheet, TakeoffMeasurement


SHEET_NUMBER_PATTERNS = [
    re.compile(r"\b([ASRD]\d(?:\.\d)?)\b", re.IGNORECASE),
    re.compile(r"\b([A-Z]{1,2}\d(?:\.\d)?)\b"),
]

SCALE_PATTERNS = [
    r'1/4"\s*=\s*1[-\'"]?-?0["\']?',
    r'1/8"\s*=\s*1[-\'"]?-?0["\']?',
    r'3/16"\s*=\s*1[-\'"]?-?0["\']?',
    r'1"\s*=\s*10[\'"]',
    r"not to scale",
    r"n\.t\.s\.",
]


def sanitize_filename(filename: str) -> str:
    path = Path(filename)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)
    stem = re.sub(r"_+", "_", stem).strip("._")
    suffix = path.suffix.lower()
    if not stem:
        stem = "blueprint"
    return f"{stem}{suffix or '.pdf'}"


def save_uploaded_blueprint(uploaded_file, upload_dir: str) -> dict:
    target_dir = Path(upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    original_file_name = getattr(uploaded_file, "name", "blueprint.pdf")
    safe_name = sanitize_filename(original_file_name)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = target_dir / unique_name

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    with file_path.open("wb") as target:
        shutil.copyfileobj(uploaded_file, target)

    file_size_bytes = file_path.stat().st_size
    return {
        "original_file_name": original_file_name,
        "stored_file_name": unique_name,
        "file_path": str(file_path),
        "file_type": Path(original_file_name).suffix.lower().lstrip("."),
        "file_size_bytes": file_size_bytes,
    }


def extract_pdf_text(file_path: str) -> dict[str, Any]:
    if fitz is None:  # pragma: no cover - exercised when dependency missing
        raise ImportError("PyMuPDF is required to extract PDF text.")

    document = fitz.open(file_path)
    pages = []
    page_texts = []
    try:
        for index in range(document.page_count):
            page = document.load_page(index)
            text = page.get_text("text").strip()
            page_texts.append(text)
            pages.append(
                {
                    "page_number": index + 1,
                    "text": text,
                }
            )
    finally:
        document.close()
    return {
        "sheet_count": len(pages),
        "full_text": "\n\n".join(page_texts).strip(),
        "pages": pages,
    }


def _detect_sheet_type(page_text: str) -> str:
    text = page_text.lower()
    if "roof plan" in text:
        return "roof_plan"
    if "exterior elevation" in text or "elevation" in text:
        return "exterior_elevation"
    if "siding" in text:
        return "siding_detail"
    if "general notes" in text:
        return "general_notes"
    if "detail" in text:
        return "detail"
    return "unknown"


def _detect_scale_text(page_text: str) -> str | None:
    text = page_text.lower().replace(" ", "")
    for pattern in SCALE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return re.search(pattern, page_text, re.IGNORECASE).group(0) if re.search(pattern, page_text, re.IGNORECASE) else None
    return None


def _detect_sheet_number(page_text: str) -> str | None:
    for pattern in SHEET_NUMBER_PATTERNS:
        match = pattern.search(page_text)
        if match:
            return match.group(1).upper()
    return None


def _detect_sheet_name(page_text: str) -> str | None:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    for line in lines[:8]:
        lowered = line.lower()
        if any(keyword in lowered for keyword in ["roof plan", "exterior elevation", "siding", "detail", "general notes"]):
            return line[:255]
    return lines[0][:255] if lines else None


def detect_sheet_metadata(page_text: str, page_number: int) -> dict[str, Any]:
    sheet_type = _detect_sheet_type(page_text)
    scale_text = _detect_scale_text(page_text)
    sheet_number = _detect_sheet_number(page_text)
    sheet_name = _detect_sheet_name(page_text)
    confidence = 0.35
    if sheet_type != "unknown":
        confidence += 0.25
    if sheet_number:
        confidence += 0.2
    if scale_text:
        confidence += 0.2
    return {
        "page_number": page_number,
        "sheet_number": sheet_number,
        "sheet_name": sheet_name,
        "sheet_type": sheet_type,
        "scale_text": scale_text,
        "calibrated_scale": None,
        "confidence_score": round(min(confidence, 1.0), 2),
        "text_preview": page_text[:250].strip(),
    }


def create_blueprint_sheets_from_pdf(session, blueprint_file_id: int, pages: list[dict[str, Any]]) -> list[BlueprintSheet]:
    created_sheets: list[BlueprintSheet] = []
    for page in pages:
        metadata = detect_sheet_metadata(page.get("text", ""), int(page.get("page_number", 0)))
        blueprint_sheet = BlueprintSheet(
            blueprint_file_id=blueprint_file_id,
            page_number=metadata["page_number"],
            sheet_number=metadata["sheet_number"],
            sheet_name=metadata["sheet_name"],
            sheet_type=metadata["sheet_type"],
            scale_text=metadata["scale_text"],
            calibrated_scale=metadata["calibrated_scale"],
            extracted_text=page.get("text", ""),
            confidence_score=metadata["confidence_score"],
        )
        session.add(blueprint_sheet)
        created_sheets.append(blueprint_sheet)
    session.flush()
    return created_sheets


def get_relevant_sheets(session, project_id: int, trade: str) -> list[BlueprintSheet]:
    blueprint_files = (
        session.query(BlueprintFile)
        .filter(BlueprintFile.project_id == project_id, BlueprintFile.is_active.is_(True))
        .order_by(BlueprintFile.uploaded_at.desc())
        .all()
    )
    if not blueprint_files:
        return []

    file_ids = [item.id for item in blueprint_files]
    sheets = (
        session.query(BlueprintSheet)
        .filter(BlueprintSheet.blueprint_file_id.in_(file_ids))
        .order_by(BlueprintSheet.page_number.asc())
        .all()
    )
    relevant_types = {
        "roofing": {"roof_plan", "general_notes", "detail", "unknown"},
        "siding": {"exterior_elevation", "siding_detail", "general_notes", "detail", "unknown"},
    }.get(trade, {"unknown"})
    keyword_map = {
        "roofing": "roof",
        "siding": "siding",
    }
    keyword = keyword_map.get(trade, trade)
    filtered: list[BlueprintSheet] = []
    for sheet in sheets:
        text = (sheet.extracted_text or "").lower()
        if sheet.sheet_type in relevant_types and (sheet.sheet_type != "unknown" or keyword in text):
            filtered.append(sheet)
    return filtered
