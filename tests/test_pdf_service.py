from __future__ import annotations

import struct
import zlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, CompanySettings, Customer, Project, Quote, QuoteLineItem, QuoteLaborLineItem
from src.pdf_service import generate_proposal_pdf
from src.proposal_service import create_or_update_proposal


def _session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _write_png(path: Path, width: int, height: int, rgba: tuple[int, int, int, int] = (0, 0, 0, 255)) -> None:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + chunk_type
            + data
            + struct.pack("!I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    r, g, b, a = rgba
    row = bytes([0] + [r, g, b, a] * width)
    raw = row * height
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, level=9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _seed_quote(session) -> Quote:
    customer = Customer(name="Jordan Smith")
    session.add(customer)
    session.flush()
    project = Project(
        customer_id=customer.id,
        project_name="Sample Project",
        project_type="new_construction",
        trade_scope="roofing",
        address="123 Main St",
        status="estimating",
    )
    session.add(project)
    session.flush()
    quote = Quote(
        project_id=project.id,
        quote_name="Sample Quote",
        status="draft",
        target_margin=0.40,
        tax_rate=0,
        permit_cost=0,
        disposal_cost=0,
        equipment_cost=0,
        overhead_cost=0,
        material_cost=1000,
        labor_cost=500,
        total_cost=1500,
        customer_price=2500,
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteLineItem(
            quote_id=quote.id,
            trade="roofing",
            item_type="material",
            description="Architectural shingles",
            quantity=10,
            unit="square",
            unit_cost=145,
            waste_factor=0.10,
            complexity_multiplier=1.0,
            line_cost=1595,
        )
    )
    session.add(
        QuoteLaborLineItem(
            quote_id=quote.id,
            trade="roofing",
            labor_method="unit_based",
            task_name="Roof install architectural shingles",
            quantity=10,
            unit="square",
            base_rate=125,
            complexity_multiplier=1.0,
            minimum_charge=0,
            calculated_cost=1250,
            final_cost=1250,
            notes="",
        )
    )
    session.commit()
    return quote


def test_generate_proposal_pdf_creates_pdf_file(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    proposal = create_or_update_proposal(session, quote.id)

    pdf_path = generate_proposal_pdf(session, proposal.id)

    pdf_file = Path(pdf_path)
    assert pdf_file.exists()
    assert pdf_file.suffix == ".pdf"
    assert pdf_file.stat().st_size > 0


def test_generate_proposal_pdf_clamps_tall_logo(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    proposal = create_or_update_proposal(session, quote.id)

    logo_path = tmp_path / "tall-logo.png"
    _write_png(logo_path, width=40, height=1200)

    company_settings = session.query(CompanySettings).first()
    if company_settings is None:
        company_settings = CompanySettings(company_name="Test Company", logo_path=str(logo_path))
        session.add(company_settings)
    else:
        company_settings.logo_path = str(logo_path)
    session.commit()

    pdf_path = generate_proposal_pdf(session, proposal.id)

    pdf_file = Path(pdf_path)
    assert pdf_file.exists()
    assert pdf_file.suffix == ".pdf"
    assert pdf_file.stat().st_size > 0
