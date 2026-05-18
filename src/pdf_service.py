from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.models import CompanySettings, Proposal


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "exports" / "proposals"


def _money(value: float | None) -> str:
    return f"${float(value or 0):,.2f}"


def _paragraph(text: str | None, style: ParagraphStyle) -> Paragraph:
    cleaned = escape(text or "").replace("\n", "<br/>")
    return Paragraph(cleaned or "&nbsp;", style)


def _safe_path(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    return candidate if candidate.exists() else None


def _header_table(company: CompanySettings, proposal: Proposal, quote) -> Table:
    styles = getSampleStyleSheet()
    company_lines = [
        f"<b>{escape(company.company_name or 'Exterior Quote Assistant')}</b>",
        escape(company.phone or ""),
        escape(company.email or ""),
        escape(company.website or ""),
        escape(company.address or ""),
    ]
    company_flow = Paragraph("<br/>".join(line for line in company_lines if line), styles["BodyText"])

    proposal_lines = [
        f"<b>Proposal #{escape(proposal.proposal_number)}</b>",
        f"Proposal Date: {proposal.created_at:%B %d, %Y}",
    ]
    expiration_days = company.default_quote_expiration_days or 30
    expiration_date = (quote.created_at + timedelta(days=expiration_days)).date() if quote.created_at else None
    if expiration_date:
        proposal_lines.append(f"Quote Expiration: {expiration_date:%B %d, %Y}")
    proposal_flow = Paragraph("<br/>".join(proposal_lines), styles["BodyText"])

    logo_path = _safe_path(company.logo_path)
    if logo_path:
        logo = Image(str(logo_path))
        logo.drawHeight = 0.9 * inch
        logo.drawWidth = min(1.8 * inch, logo.imageWidth * (logo.drawHeight / logo.imageHeight))
    else:
        logo = Paragraph("&nbsp;", styles["BodyText"])

    return Table(
        [[logo, company_flow, proposal_flow]],
        colWidths=[1.9 * inch, 3.8 * inch, 2.0 * inch],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        ),
    )


def _trade_scope_label(project) -> str:
    if project.trade_scope == "combination":
        return "Roofing and Siding"
    return project.trade_scope.replace("_", " ").title()


def _info_table(label_value_pairs: list[tuple[str, str]]) -> Table:
    rows = [[Paragraph(f"<b>{escape(label)}</b>", getSampleStyleSheet()["BodyText"]), Paragraph(escape(value), getSampleStyleSheet()["BodyText"])] for label, value in label_value_pairs]
    return Table(
        rows,
        colWidths=[1.6 * inch, 6.2 * inch],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7DE")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        ),
    )


def _section(title: str, body: str, style: ParagraphStyle) -> list:
    return [
        Paragraph(escape(title), style),
        Spacer(1, 0.08 * inch),
        _paragraph(body, getSampleStyleSheet()["BodyText"]),
    ]


def generate_proposal_pdf(session, proposal_id: int) -> str:
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id} was not found.")

    quote = proposal.quote
    project = quote.project
    customer = project.customer
    company = session.query(CompanySettings).order_by(CompanySettings.id.asc()).first()
    if company is None:
        raise ValueError("Company settings are required before generating a proposal PDF.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT_DIR / f"proposal_{proposal.proposal_number}.pdf"

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
            spaceBefore=10,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontSize=9,
            textColor=colors.HexColor("#4B5563"),
        )
    )

    story: list = [
        _header_table(company, proposal, quote),
        Spacer(1, 0.18 * inch),
        Paragraph(escape(proposal.title), styles["Heading1"]),
        Spacer(1, 0.1 * inch),
        _paragraph(proposal.intro_text or "", styles["BodyText"]),
        Spacer(1, 0.12 * inch),
    ]

    customer_rows = [
        ("Bill To", customer.name),
        ("Customer Company", customer.company_name or ""),
        ("Phone", customer.phone or ""),
        ("Email", customer.email or ""),
        ("Project Address", project.address or customer.address or ""),
    ]
    story.extend(
        [
            Paragraph("Customer Information", styles["SectionHeading"]),
            _info_table(customer_rows),
            Paragraph("Project Information", styles["SectionHeading"]),
            _info_table(
                [
                    ("Project Name", project.project_name),
                    ("Project Type", project.project_type.replace("_", " ").title()),
                    ("Trade Scope", _trade_scope_label(project)),
                    ("Quote Name", quote.quote_name),
                ]
            ),
        ]
    )

    for title, body in [
        ("Project Summary", proposal.intro_text or ""),
        ("Scope of Work", proposal.scope_text or ""),
        ("Material Summary", proposal.material_summary_text or ""),
        ("Labor Summary", proposal.labor_summary_text or ""),
        ("Assumptions", proposal.assumptions_text or ""),
        ("Exclusions", proposal.exclusions_text or ""),
        ("Change Order Terms", proposal.change_order_text or ""),
        ("Payment Terms", proposal.payment_terms or ""),
        ("Warranty", proposal.warranty_text or ""),
        ("Total Investment", proposal.total_investment_text or _money(quote.customer_price)),
    ]:
        story.extend(_section(title, body, styles["SectionHeading"]))
        story.append(Spacer(1, 0.06 * inch))

    approval_table = Table(
        [
            [Paragraph("<b>Customer Signature</b>", styles["BodyText"]), Paragraph("&nbsp;", styles["BodyText"])],
            [Paragraph("<b>Date</b>", styles["BodyText"]), Paragraph("&nbsp;", styles["BodyText"])],
            [Paragraph("<b>Accepted Proposal Amount</b>", styles["BodyText"]), Paragraph(escape(_money(quote.customer_price)), styles["BodyText"])],
        ],
        colWidths=[2.0 * inch, 5.8 * inch],
        style=TableStyle(
            [
                ("LINEBELOW", (1, 0), (1, 0), 0.75, colors.black),
                ("LINEBELOW", (1, 1), (1, 1), 0.75, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )
    story.extend([Paragraph("Approval", styles["SectionHeading"]), approval_table])

    footer_text = company.default_footer_text or ""
    if footer_text:
        story.extend([Spacer(1, 0.15 * inch), Paragraph(escape(footer_text), styles["SmallMuted"])])

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=proposal.title,
        author=company.company_name or "",
    )
    doc.build(story)

    proposal.pdf_path = str(pdf_path)
    session.commit()
    session.refresh(proposal)
    return str(pdf_path)
