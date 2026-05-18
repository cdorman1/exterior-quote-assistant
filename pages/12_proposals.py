from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import Proposal, Quote
from src.pdf_service import generate_proposal_pdf
from src.proposal_service import create_or_update_proposal


def _latest_proposal(session, quote_id: int) -> Proposal | None:
    return (
        session.query(Proposal)
        .filter(Proposal.quote_id == quote_id)
        .order_by(Proposal.updated_at.desc(), Proposal.created_at.desc(), Proposal.id.desc())
        .first()
    )


require_auth()
st.title("Proposals")
init_db()
db = SessionLocal()
try:
    quotes = db.query(Quote).order_by(Quote.created_at.desc()).all()
    if not quotes:
        st.info("No saved quotes yet.")
        st.stop()

    quote_options = {f"{quote.quote_name} ({quote.id})": quote for quote in quotes}
    selected_quote = quote_options[st.selectbox("Select quote", list(quote_options))]
    proposal = _latest_proposal(db, selected_quote.id)

    summary_cols = st.columns(4)
    summary_cols[0].metric("Quote ID", selected_quote.id)
    summary_cols[1].metric("Customer", selected_quote.project.customer.name)
    summary_cols[2].metric("Project", selected_quote.project.project_name)
    summary_cols[3].metric("Customer price", f"${selected_quote.customer_price:,.2f}")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Quote ID": selected_quote.id,
                    "Project name": selected_quote.project.project_name,
                    "Customer name": selected_quote.project.customer.name,
                    "Trade scope": selected_quote.project.trade_scope,
                    "Customer price": selected_quote.customer_price,
                    "Proposal number": proposal.proposal_number if proposal else "",
                    "Proposal status": proposal.status if proposal else "none",
                    "PDF path": proposal.pdf_path if proposal else "",
                }
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Generate Proposal Draft"):
        proposal = create_or_update_proposal(db, selected_quote.id)
        st.success(f"Proposal draft {proposal.proposal_number} generated.")
        st.rerun()

    if proposal:
        st.subheader("Proposal editor")
        with st.form(f"proposal_editor_{proposal.id}"):
            status = st.selectbox(
                "Status",
                ["draft", "generated", "sent", "accepted", "rejected", "void"],
                index=["draft", "generated", "sent", "accepted", "rejected", "void"].index(proposal.status or "draft"),
            )
            title = st.text_input("Title", value=proposal.title or "")
            intro_text = st.text_area("Intro text", value=proposal.intro_text or "", height=120)
            scope_text = st.text_area("Scope text", value=proposal.scope_text or "", height=160)
            material_summary_text = st.text_area("Material summary text", value=proposal.material_summary_text or "", height=120)
            labor_summary_text = st.text_area("Labor summary text", value=proposal.labor_summary_text or "", height=120)
            assumptions_text = st.text_area("Assumptions text", value=proposal.assumptions_text or "", height=120)
            exclusions_text = st.text_area("Exclusions text", value=proposal.exclusions_text or "", height=120)
            change_order_text = st.text_area("Change order text", value=proposal.change_order_text or "", height=120)
            payment_terms = st.text_area("Payment terms", value=proposal.payment_terms or "", height=120)
            warranty_text = st.text_area("Warranty text", value=proposal.warranty_text or "", height=120)
            total_investment_text = st.text_input("Total investment text", value=proposal.total_investment_text or "")
            save_clicked = st.form_submit_button("Save Proposal Draft")

        if save_clicked:
            proposal.status = status
            proposal.title = title
            proposal.intro_text = intro_text
            proposal.scope_text = scope_text
            proposal.material_summary_text = material_summary_text
            proposal.labor_summary_text = labor_summary_text
            proposal.assumptions_text = assumptions_text
            proposal.exclusions_text = exclusions_text
            proposal.change_order_text = change_order_text
            proposal.payment_terms = payment_terms
            proposal.warranty_text = warranty_text
            proposal.total_investment_text = total_investment_text
            db.commit()
            st.success("Proposal saved.")
            st.rerun()

        pdf_path = proposal.pdf_path
        col_a, col_b = st.columns([1, 1])
        if col_a.button("Generate PDF"):
            pdf_path = generate_proposal_pdf(db, proposal.id)
            st.success(f"PDF generated at {pdf_path}.")
            st.rerun()

        if pdf_path:
            st.caption(f"PDF path: {pdf_path}")
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                col_b.download_button(
                    label="Download PDF",
                    data=pdf_file.read_bytes(),
                    file_name=pdf_file.name,
                    mime="application/pdf",
                )
    else:
        st.info("Generate a proposal draft from the selected quote to begin editing.")
finally:
    db.close()
