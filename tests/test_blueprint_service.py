from __future__ import annotations

from pathlib import Path

import fitz

from src.blueprint_service import detect_sheet_metadata, extract_pdf_text, sanitize_filename


def test_sanitize_filename_removes_unsafe_characters():
    assert sanitize_filename("../../My Blueprint #1 (rev).pdf") == "My_Blueprint_1_rev.pdf"


def test_extract_pdf_text_returns_sheet_count_and_pages(tmp_path):
    pdf_path = Path(tmp_path) / "sample.pdf"
    document = fitz.open()
    page1 = document.new_page()
    page1.insert_text((72, 72), "A1.0 Roof Plan\nScale: 1/4\" = 1'-0\"")
    page2 = document.new_page()
    page2.insert_text((72, 72), "A2.1 Exterior Elevation\nNot to scale")
    document.save(pdf_path)
    document.close()

    result = extract_pdf_text(str(pdf_path))

    assert result["sheet_count"] == 2
    assert len(result["pages"]) == 2
    assert "Roof Plan" in result["full_text"]
    assert "Exterior Elevation" in result["full_text"]


def test_detect_sheet_metadata_detects_roof_plan_and_scale():
    metadata = detect_sheet_metadata("A1.0 Roof Plan\nScale: 1/4\" = 1'-0\"", 1)
    assert metadata["sheet_type"] == "roof_plan"
    assert metadata["scale_text"]


def test_detect_sheet_metadata_detects_exterior_elevation():
    metadata = detect_sheet_metadata("A2.1 Exterior Elevation", 2)
    assert metadata["sheet_type"] == "exterior_elevation"


def test_detect_sheet_metadata_detects_unknown_for_unrecognized_text():
    metadata = detect_sheet_metadata("Random notes about project scope", 3)
    assert metadata["sheet_type"] == "unknown"
