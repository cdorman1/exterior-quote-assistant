from __future__ import annotations

from pathlib import Path

import fitz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.blueprint_service import render_pdf_sheet_to_image
from src.models import (
    Base,
    BlueprintFile,
    BlueprintSheet,
    Customer,
    Project,
    Quote,
    QuoteMeasurementLink,
    TakeoffExtractionRun,
    TakeoffMeasurement,
)
from src.takeoff_extraction_service import link_quote_measurements, run_auto_takeoff


def _session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _make_pdf(path: Path) -> Path:
    pdf_path = path / "sample-blueprint.pdf"
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 72), "A2.1 Exterior Elevation\nScale: 1/4\" = 1'-0\"\nWall A 20 ft x 10 ft")
    document.save(pdf_path)
    document.close()
    return pdf_path


def _seed_blueprint_sheet(session, tmp_path: Path) -> BlueprintSheet:
    pdf_path = _make_pdf(tmp_path)
    customer = Customer(name="Jordan Smith")
    session.add(customer)
    session.flush()
    project = Project(
        customer_id=customer.id,
        project_name="Sample Project",
        project_type="new_construction",
        trade_scope="siding",
    )
    session.add(project)
    session.flush()
    blueprint_file = BlueprintFile(
        project_id=project.id,
        original_file_name="sample-blueprint.pdf",
        stored_file_name="sample-blueprint.pdf",
        file_path=str(pdf_path),
        file_type="pdf",
        file_size_bytes=pdf_path.stat().st_size,
        sheet_count=1,
        is_active=True,
    )
    session.add(blueprint_file)
    session.flush()
    sheet = BlueprintSheet(
        blueprint_file_id=blueprint_file.id,
        page_number=1,
        sheet_number="A2.1",
        sheet_name="Exterior Elevation",
        sheet_type="exterior_elevation",
        scale_text="1/4\" = 1'-0\"",
    )
    session.add(sheet)
    session.commit()
    return sheet


def test_render_pdf_sheet_to_image_writes_high_resolution_png(tmp_path):
    pdf_path = _make_pdf(tmp_path)
    output_path = render_pdf_sheet_to_image(str(pdf_path), page_number=1, output_dir=str(tmp_path / "renders"), dpi=200)

    rendered = Path(output_path)
    assert rendered.exists()
    assert rendered.suffix == ".png"
    assert rendered.stat().st_size > 0


def test_run_auto_takeoff_persists_unapproved_draft_measurement(tmp_path):
    session = _session(tmp_path)
    sheet = _seed_blueprint_sheet(session, tmp_path)

    def fake_extractor(image_path: str, trade_hint: str | None = None) -> dict:
        assert Path(image_path).exists()
        assert trade_hint == "siding"
        return {
            "trade": "siding",
            "detected_measurements": [
                {
                    "label": "Wall A",
                    "measurement_type": "siding_wall_area",
                    "shape": "rectangle",
                    "width_ft": 20,
                    "height_ft": 10,
                    "confidence": 0.88,
                    "source_text": "Wall A 20 ft x 10 ft",
                }
            ],
            "openings": [],
            "calculation_recommendations": ["Review Wall A before approving."],
            "warnings": [],
            "confidence": 0.88,
        }

    result = run_auto_takeoff(
        session,
        blueprint_sheet_id=sheet.id,
        trade_hint="siding",
        render_dir=str(tmp_path / "renders"),
        extractor=fake_extractor,
    )

    assert result["created_count"] == 1
    saved = session.query(TakeoffMeasurement).one()
    assert saved.project_id == sheet.blueprint_file.project_id
    assert saved.blueprint_file_id == sheet.blueprint_file_id
    assert saved.blueprint_sheet_id == sheet.id
    assert saved.trade == "siding"
    assert saved.measurement_type == "siding_wall_area"
    assert saved.quantity == 200
    assert saved.unit == "square_foot"
    assert saved.source == "openai_vision_extracted"
    assert saved.approved is False
    assert saved.confidence_score == 0.88
    assert "Wall A" in (saved.notes or "")
    assert "Review Wall A" in (saved.notes or "")


def test_auto_takeoff_handles_opening_deductions_lines_counts_audit_and_overlays(tmp_path):
    session = _session(tmp_path)
    sheet = _seed_blueprint_sheet(session, tmp_path)

    def fake_extractor(image_path: str, trade_hint: str | None = None) -> dict:
        return {
            "trade": "siding",
            "detected_measurements": [
                {
                    "label": "Wall with windows",
                    "measurement_type": "siding_wall_area",
                    "shape": "rectangle",
                    "width_ft": 30,
                    "height_ft": 10,
                    "deduct_openings": True,
                    "openings": [
                        {"label": "Window", "quantity": 2, "width_ft": 3, "height_ft": 4},
                        {"label": "Door", "quantity": 1, "width_ft": 3, "height_ft": 7},
                    ],
                    "overlay_points": [[10, 10], [110, 10], [110, 70], [10, 70]],
                    "confidence": 0.9,
                },
                {
                    "label": "Gable",
                    "measurement_type": "gable_area",
                    "shape": "polygon",
                    "points_ft": [[0, 0], [20, 0], [10, 8]],
                    "confidence": 0.8,
                },
                {
                    "label": "Eave trim",
                    "measurement_type": "eave_length",
                    "shape": "polyline",
                    "segments_ft": [12, 8, 10],
                    "confidence": 0.75,
                },
                {
                    "label": "Exterior lights",
                    "measurement_type": "fixture_count",
                    "shape": "count",
                    "quantity": 4,
                    "confidence": 0.7,
                },
            ],
            "warnings": [],
            "confidence": 0.84,
        }

    result = run_auto_takeoff(
        session,
        blueprint_sheet_id=sheet.id,
        trade_hint="siding",
        render_dir=str(tmp_path / "renders"),
        overlay_dir=str(tmp_path / "overlays"),
        extractor=fake_extractor,
    )

    assert result["created_count"] == 4
    assert Path(result["overlay_path"]).exists()
    assert session.query(TakeoffExtractionRun).count() == 1
    run = session.query(TakeoffExtractionRun).one()
    assert run.status == "completed"
    assert run.created_measurement_count == 4
    assert run.overlay_path == result["overlay_path"]
    measurements = {item.measurement_type: item for item in session.query(TakeoffMeasurement).all()}
    assert measurements["siding_wall_area"].quantity == 255
    assert "Opening deductions: 45" in (measurements["siding_wall_area"].notes or "")
    assert measurements["gable_area"].quantity == 80
    assert measurements["eave_length"].quantity == 30
    assert measurements["eave_length"].unit == "linear_foot"
    assert measurements["fixture_count"].quantity == 4
    assert measurements["fixture_count"].unit == "each"


def test_link_quote_measurements_creates_join_rows_without_notes_parsing(tmp_path):
    session = _session(tmp_path)
    sheet = _seed_blueprint_sheet(session, tmp_path)
    quote = Quote(
        project_id=sheet.blueprint_file.project_id,
        quote_name="Draft Quote",
        status="draft",
        target_margin=0.4,
    )
    measurement = TakeoffMeasurement(
        project_id=sheet.blueprint_file.project_id,
        blueprint_file_id=sheet.blueprint_file_id,
        blueprint_sheet_id=sheet.id,
        trade="siding",
        measurement_type="siding_wall_area",
        quantity=255,
        unit="square_foot",
        source="openai_vision_extracted",
        approved=True,
    )
    session.add_all([quote, measurement])
    session.commit()

    created = link_quote_measurements(session, quote.id, [measurement.id], usage="material_quantity")

    assert created == 1
    link = session.query(QuoteMeasurementLink).one()
    assert link.quote_id == quote.id
    assert link.takeoff_measurement_id == measurement.id
    assert link.usage == "material_quantity"
