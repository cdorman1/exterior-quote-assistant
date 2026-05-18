from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.models import CompanySettings, Proposal, Quote


DEFAULT_PAYMENT_TERMS = (
    "Deposit due upon approval. Final payment due upon completion unless otherwise agreed in writing."
)
DEFAULT_WARRANTY_TEXT = (
    "Manufacturer warranties apply to selected materials. Workmanship warranty is provided according to company policy."
)
DEFAULT_FOOTER_TEXT = "Thank you for the opportunity to provide this proposal."
DEFAULT_ASSUMPTIONS = (
    "This proposal is based on the approved measurements, project information, plan documents if applicable, and current material pricing available at the time of quote. Final field verification may be required before material ordering. Pricing assumes normal site access unless otherwise noted."
)
DEFAULT_EXCLUSIONS = (
    "This proposal excludes hidden rot repair, structural framing repair, code required changes not shown in the approved scope, electrical relocation, permit fees unless listed, and any work not specifically included in the written scope."
)
DEFAULT_CHANGE_ORDER_TEXT = (
    "Any work outside the approved scope will require a written change order. Change orders may include additional labor, materials, disposal, equipment, access costs, plan revision changes, or customer requested upgrades."
)


def _money(value: float | None) -> str:
    return f"${float(value or 0):,.2f}"


def _text_items(items: list[Any], *, label_keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for item in items:
        for key in label_keys:
            if isinstance(item, dict):
                value = item.get(key)
            else:
                value = getattr(item, key, None)
            if value:
                values.append(str(value).strip())
                break
    return values


def _unique_preserve_order(items: list[str]) -> list[str]:
    ordered = OrderedDict()
    for item in items:
        normalized = item.strip()
        if normalized and normalized.lower() not in ordered:
            ordered[normalized.lower()] = normalized
    return list(ordered.values())


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _combined_text(*items: Any) -> str:
    return " ".join(
        str(value).lower()
        for item in items
        for value in (
            [getattr(item, "description", None), getattr(item, "task_name", None), getattr(item, "notes", None)]
            if not isinstance(item, dict)
            else [item.get("description"), item.get("task_name"), item.get("notes")]
        )
        if value
    )


def generate_proposal_number(quote_id: int) -> str:
    return f"PROP-{date.today():%Y%m%d}-{quote_id}"


def _trade_scope_label(project) -> str:
    if project.trade_scope == "combination":
        return "roofing and siding"
    return project.trade_scope.replace("_", " ")


def build_project_summary(customer, project, quote) -> str:
    scope = _trade_scope_label(project)
    return (
        f"This proposal covers the {scope} scope for {project.project_name}. "
        f"Pricing is based on approved measurements, selected materials, labor scope, and current pricing available at the time of proposal."
    )


def build_scope_text(project, quote, quote_line_items, labor_line_items) -> str:
    project_scope = project.trade_scope
    source_text = _combined_text(*quote_line_items, *labor_line_items, project, quote)

    roofing_lines = [
        ("Roofing system installation", ["roof install", "roofing system", "roofing"]),
        ("Underlayment", ["underlayment"]),
        ("Ice and water shield", ["ice and water", "water shield"]),
        ("Starter shingles", ["starter shingles", "starter strip"]),
        ("Architectural shingles", ["architectural shingle", "shingle"]),
        ("Ridge cap", ["ridge cap"]),
        ("Ridge vent", ["ridge vent"]),
        ("Drip edge", ["drip edge"]),
        ("Flashing", ["flashing", "pipe boot"]),
        ("Cleanup and disposal", ["tear off", "cleanup", "disposal", "demo"]),
    ]
    siding_lines = [
        ("House wrap", ["house wrap"]),
        ("Siding installation", ["siding install", "vinyl siding", "fiber cement"]),
        ("Starter strip", ["starter strip"]),
        ("J channel", ["j channel"]),
        ("Outside corners", ["outside corner"]),
        ("Inside corners", ["inside corner"]),
        ("Trim package", ["trim", "corner package"]),
        ("Soffit", ["soffit"]),
        ("Fascia", ["fascia"]),
        ("Cleanup and disposal", ["tear off", "cleanup", "disposal", "demo"]),
    ]

    def _build_section(title: str, rules: list[tuple[str, list[str]]], fallback_items: list[str]) -> str:
        selected = [label for label, keywords in rules if _contains_any(source_text, keywords)]
        if not selected:
            selected = fallback_items
        bullets = "\n".join(f"- {item}" for item in selected)
        return f"{title}\n{bullets}"

    sections: list[str] = []
    if project_scope in {"roofing", "combination"}:
        sections.append(
            _build_section(
                "Roofing",
                roofing_lines,
                [
                    "Roofing system installation",
                    "Underlayment",
                    "Ice and water shield",
                    "Starter shingles",
                    "Architectural shingles",
                    "Ridge cap",
                    "Ridge vent",
                    "Drip edge",
                    "Flashing",
                    "Cleanup and disposal",
                ],
            )
        )
    if project_scope in {"siding", "combination"}:
        sections.append(
            _build_section(
                "Siding",
                siding_lines,
                [
                    "House wrap",
                    "Siding installation",
                    "Starter strip",
                    "J channel",
                    "Outside corners",
                    "Inside corners",
                    "Trim package",
                    "Soffit",
                    "Fascia",
                    "Cleanup and disposal",
                ],
            )
        )

    if not sections:
        return (
            "This proposal covers the approved exterior scope for the project listed above. "
            "The final installation scope will follow the approved measurements and selected materials."
        )

    return "\n\n".join(sections)


def build_material_summary_text(quote_line_items) -> str:
    material_descriptions = _unique_preserve_order(
        _text_items(list(quote_line_items), label_keys=("description",))
    )
    if material_descriptions:
        return (
            "Materials included may include "
            + ", ".join(material_descriptions)
            + " and related accessories as applicable to the approved scope."
        )
    return (
        "Materials included may include architectural shingles, underlayment, drip edge, ridge cap, siding panels, house wrap, starter strip, J channel, trim, soffit, fascia, fasteners, and related accessories as applicable to the approved scope."
    )


def build_labor_summary_text(labor_line_items) -> str:
    labor_names = _unique_preserve_order(
        _text_items(list(labor_line_items), label_keys=("task_name",))
    )
    if labor_names:
        return (
            "Labor includes preparation, layout, installation, accessory installation, project cleanup, and related installation work required for the approved scope. "
            "Approved labor tasks may include " + ", ".join(labor_names) + "."
        )
    return (
        "Labor includes preparation, layout, installation, accessory installation, project cleanup, and related installation work required for the approved scope."
    )


def build_default_assumptions(project, quote) -> str:
    return DEFAULT_ASSUMPTIONS


def build_default_exclusions(project, quote) -> str:
    return DEFAULT_EXCLUSIONS


def build_default_change_order_text() -> str:
    return DEFAULT_CHANGE_ORDER_TEXT


def build_total_investment_text(quote) -> str:
    return f"Total proposal amount: {_money(getattr(quote, 'customer_price', 0))}"


def _get_company_settings(session: Session) -> CompanySettings:
    settings = session.query(CompanySettings).order_by(CompanySettings.id.asc()).first()
    if settings is None:
        settings = CompanySettings(
            company_name="Exterior Quote Assistant Demo Company",
            phone="",
            email="",
            website="",
            address="",
            logo_path=None,
            license_number="",
            insurance_text="",
            default_quote_expiration_days=30,
            default_payment_terms=DEFAULT_PAYMENT_TERMS,
            default_warranty_text=DEFAULT_WARRANTY_TEXT,
            default_footer_text=DEFAULT_FOOTER_TEXT,
        )
        session.add(settings)
        session.flush()
    return settings


def create_or_update_proposal(session: Session, quote_id: int) -> Proposal:
    quote = session.get(Quote, quote_id)
    if quote is None:
        raise ValueError(f"Quote {quote_id} was not found.")

    proposal = (
        session.query(Proposal)
        .filter(Proposal.quote_id == quote_id)
        .order_by(Proposal.created_at.desc(), Proposal.id.desc())
        .first()
    )
    if proposal and proposal.status in {"accepted", "sent"}:
        return proposal

    settings = _get_company_settings(session)
    project = quote.project
    customer = project.customer
    quote_line_items = list(quote.line_items)
    labor_line_items = list(quote.labor_line_items)

    fields = {
        "proposal_number": proposal.proposal_number if proposal else generate_proposal_number(quote.id),
        "status": proposal.status if proposal else "draft",
        "title": f"Proposal for {project.project_name}",
        "intro_text": build_project_summary(customer, project, quote),
        "scope_text": build_scope_text(project, quote, quote_line_items, labor_line_items),
        "material_summary_text": build_material_summary_text(quote_line_items),
        "labor_summary_text": build_labor_summary_text(labor_line_items),
        "assumptions_text": build_default_assumptions(project, quote),
        "exclusions_text": build_default_exclusions(project, quote),
        "change_order_text": build_default_change_order_text(),
        "payment_terms": settings.default_payment_terms or DEFAULT_PAYMENT_TERMS,
        "warranty_text": settings.default_warranty_text or DEFAULT_WARRANTY_TEXT,
        "total_investment_text": build_total_investment_text(quote),
        "pdf_path": None if not proposal else proposal.pdf_path,
    }

    if proposal is None:
        proposal = Proposal(quote_id=quote.id, **fields)
        session.add(proposal)
    else:
        for key, value in fields.items():
            setattr(proposal, key, value)

    session.commit()
    session.refresh(proposal)
    return proposal
