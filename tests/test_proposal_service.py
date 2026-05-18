from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Customer, Project, Quote, QuoteLaborLineItem, QuoteLineItem
from src.proposal_service import (
    build_default_assumptions,
    build_default_change_order_text,
    build_default_exclusions,
    build_labor_summary_text,
    build_material_summary_text,
    build_project_summary,
    build_scope_text,
    build_total_investment_text,
    create_or_update_proposal,
    generate_proposal_number,
)


def _session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _seed_quote(session, *, trade_scope: str = "roofing") -> Quote:
    customer = Customer(name="Jordan Smith", company_name="Smith Development")
    session.add(customer)
    session.flush()
    project = Project(
        customer_id=customer.id,
        project_name="Sample Project",
        project_type="existing_construction",
        trade_scope=trade_scope,
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
        tax_rate=0.0,
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
            trade=trade_scope if trade_scope != "combination" else "roofing",
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
            trade=trade_scope if trade_scope != "combination" else "roofing",
            labor_method="unit_based",
            task_name="Roof install architectural shingles",
            quantity=10,
            unit="square",
            base_rate=125,
            complexity_multiplier=1.15,
            minimum_charge=1000,
            calculated_cost=1437.5,
            final_cost=1437.5,
            notes="",
        )
    )
    session.commit()
    return quote


def test_generate_proposal_number_returns_prop_format():
    proposal_number = generate_proposal_number(42)
    assert re.fullmatch(r"PROP-\d{8}-42", proposal_number)


def test_build_scope_text_generates_roofing_scope(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session, trade_scope="roofing")
    text = build_scope_text(quote.project, quote, quote.line_items, quote.labor_line_items)
    assert "Roofing" in text
    assert "Architectural shingles" in text or "Roofing system installation" in text


def test_build_scope_text_generates_siding_scope(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session, trade_scope="siding")
    quote.line_items[0].description = "Vinyl siding"
    quote.labor_line_items[0].task_name = "Install vinyl siding"
    session.commit()
    text = build_scope_text(quote.project, quote, quote.line_items, quote.labor_line_items)
    assert "Siding" in text
    assert "Siding installation" in text or "Vinyl siding" in text


def test_build_material_summary_text_does_not_include_raw_unit_costs():
    text = build_material_summary_text(
        [
            {
                "description": "Architectural shingles",
                "unit_cost": 145,
            }
        ]
    )
    assert "145" not in text
    assert "$" not in text


def test_build_labor_summary_text_does_not_include_raw_labor_rates():
    text = build_labor_summary_text(
        [
            {
                "task_name": "Roof install architectural shingles",
                "base_rate": 125,
                "final_cost": 1437.5,
            }
        ]
    )
    assert "125" not in text
    assert "$" not in text


def test_default_language_helpers_return_expected_text(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    assert "approved measurements" in build_default_assumptions(quote.project, quote)
    assert "hidden rot repair" in build_default_exclusions(quote.project, quote)
    assert "change order" in build_default_change_order_text().lower()


def test_build_total_investment_text_includes_formatted_price(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    assert build_total_investment_text(quote) == "Total proposal amount: $2,500.00"


def test_create_or_update_proposal_creates_proposal(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    proposal = create_or_update_proposal(session, quote.id)

    assert proposal.id is not None
    assert proposal.quote_id == quote.id
    assert proposal.status == "draft"
    assert proposal.proposal_number.startswith("PROP-")
    assert proposal.title == "Proposal for Sample Project"


def test_create_or_update_proposal_does_not_overwrite_accepted_proposal(tmp_path):
    session = _session(tmp_path)
    quote = _seed_quote(session)
    proposal = create_or_update_proposal(session, quote.id)
    proposal.status = "accepted"
    proposal.title = "Locked Title"
    session.commit()

    updated = create_or_update_proposal(session, quote.id)
    assert updated.id == proposal.id
    assert updated.title == "Locked Title"
    assert updated.status == "accepted"
