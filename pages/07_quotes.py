from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.database import SessionLocal, init_db
from src.models import ChangeOrderRate, Proposal, Quote, TakeoffMeasurement
from src.proposal_service import create_or_update_proposal
from src.proposal_generator import generate_proposal_text

require_auth()
st.title("Quotes")
init_db()
db = SessionLocal()
try:
    quotes = db.query(Quote).order_by(Quote.created_at.desc()).all()
    st.subheader("Saved quotes")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": q.id,
                    "Quote": q.quote_name,
                    "Project": q.project.project_name,
                    "Customer": q.project.customer.name,
                    "Status": q.status,
                    "Material Cost": q.material_cost,
                    "Labor Cost": q.labor_cost,
                    "Permit Cost": q.permit_cost,
                    "Disposal Cost": q.disposal_cost,
                    "Equipment Cost": q.equipment_cost,
                    "Overhead Cost": q.overhead_cost,
                    "Total Cost": q.total_cost,
                    "Customer Price": q.customer_price,
                    "Target Margin": q.target_margin,
                    "Created": q.created_at,
                }
                for q in quotes
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if quotes:
        quote_options = {f"{q.quote_name} ({q.id})": q for q in quotes}
        quote = quote_options[st.selectbox("Generate proposal text for quote", list(quote_options))]
        change_order_rates = db.query(ChangeOrderRate).all()

        st.subheader("Quote summary")
        summary_cols = st.columns(7)
        summary_cols[0].metric("Material cost", f"${quote.material_cost:,.2f}")
        summary_cols[1].metric("Labor cost", f"${quote.labor_cost:,.2f}")
        summary_cols[2].metric("Permit cost", f"${quote.permit_cost:,.2f}")
        summary_cols[3].metric("Disposal cost", f"${quote.disposal_cost:,.2f}")
        summary_cols[4].metric("Equipment cost", f"${quote.equipment_cost:,.2f}")
        summary_cols[5].metric("Overhead cost", f"${quote.overhead_cost:,.2f}")
        summary_cols[6].metric("Total cost", f"${quote.total_cost:,.2f}")
        st.metric("Customer price", f"${quote.customer_price:,.2f}")
        st.caption(f"Target margin: {quote.target_margin:.0%}")
        st.caption(f"Blueprint files on project: {len(quote.project.blueprint_files)}")
        if quote.notes:
            st.caption(quote.notes)

        latest_proposal = (
            db.query(Proposal)
            .filter(Proposal.quote_id == quote.id)
            .order_by(Proposal.updated_at.desc(), Proposal.created_at.desc(), Proposal.id.desc())
            .first()
        )
        st.subheader("Proposal status")
        if latest_proposal:
            proposal_cols = st.columns(3)
            proposal_cols[0].metric("Proposal number", latest_proposal.proposal_number)
            proposal_cols[1].metric("Status", latest_proposal.status)
            proposal_cols[2].metric("PDF path", "Saved" if latest_proposal.pdf_path else "Not generated")
            if latest_proposal.pdf_path:
                st.caption(latest_proposal.pdf_path)
        else:
            st.info("No proposal has been created for this quote yet.")

        if st.button("Create Proposal Draft"):
            proposal = create_or_update_proposal(db, quote.id)
            st.success(f"Proposal draft {proposal.proposal_number} created.")
            st.rerun()

        quantity_source_match = re.search(r"Quantity source:\s*([^;]+)", quote.notes or "", re.IGNORECASE)
        if quantity_source_match:
            st.caption(f"Quantity source: {quantity_source_match.group(1).strip()}")

        measurement_ids: list[int] = []
        measurement_match = re.search(r"blueprint measurements:\s*([0-9, ]+)", quote.notes or "", re.IGNORECASE)
        if measurement_match:
            measurement_ids = [int(item.strip()) for item in measurement_match.group(1).split(",") if item.strip().isdigit()]
        if measurement_ids:
            referenced_measurements = (
                db.query(TakeoffMeasurement)
                .filter(TakeoffMeasurement.id.in_(measurement_ids))
                .all()
            )
            if referenced_measurements:
                st.subheader("Related approved takeoff measurements")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Trade": item.trade,
                                "Measurement Type": item.measurement_type,
                                "Quantity": item.quantity,
                                "Unit": item.unit,
                                "Source": item.source,
                                "Confidence": item.confidence_score,
                                "Approved": item.approved,
                                "Notes": item.notes,
                            }
                            for item in referenced_measurements
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        st.subheader("Labor breakdown")
        labor_breakdown = pd.DataFrame(
            [
                {
                    "Trade": item.trade,
                    "Method": item.labor_method,
                    "Task": item.task_name,
                    "Quantity": item.quantity,
                    "Unit": item.unit,
                    "Base Rate": item.base_rate,
                    "Multiplier": item.complexity_multiplier,
                    "Calculated Cost": item.calculated_cost,
                    "Override Cost": item.manual_override_cost,
                    "Final Cost": item.final_cost,
                    "Override Reason": item.override_reason,
                    "Notes": item.notes,
                }
                for item in quote.labor_line_items
            ]
        )
        if labor_breakdown.empty:
            st.info("No labor line items were saved with this quote.")
        else:
            st.dataframe(labor_breakdown, use_container_width=True, hide_index=True)

        proposal = generate_proposal_text(
            quote.project.customer,
            quote.project,
            quote,
            quote.line_items,
            change_order_rates,
        )
        st.subheader("Generated proposal text")
        st.text_area("Proposal", value=proposal, height=650)
    else:
        st.info("No saved quotes yet.")
finally:
    db.close()
