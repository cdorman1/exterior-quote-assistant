from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st

from src.auth import require_auth
from src.blueprint_service import sanitize_filename
from src.database import SessionLocal, init_db
from src.models import CompanySettings


def _company_settings(session) -> CompanySettings:
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
            default_payment_terms=(
                "Deposit due upon approval. Final payment due upon completion unless otherwise agreed in writing."
            ),
            default_warranty_text=(
                "Manufacturer warranties apply to selected materials. Workmanship warranty is provided according to company policy."
            ),
            default_footer_text="Thank you for the opportunity to provide this proposal.",
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def _save_logo(uploaded_logo) -> str:
    logo_dir = Path("data/uploads/logos")
    logo_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(uploaded_logo.name)
    target_name = f"{uuid.uuid4().hex}_{safe_name}"
    target_path = logo_dir / target_name
    uploaded_logo.seek(0)
    target_path.write_bytes(uploaded_logo.getbuffer())
    return str(target_path)


require_auth()
st.title("Company Settings")
init_db()
db = SessionLocal()
try:
    settings = _company_settings(db)

    st.subheader("Company Profile")
    if settings.logo_path and Path(settings.logo_path).exists():
        st.image(str(settings.logo_path), width=220)
        st.caption("Current logo")

    with st.form("company_profile_form"):
        company_name = st.text_input("Company name", value=settings.company_name or "")
        phone = st.text_input("Phone", value=settings.phone or "")
        email = st.text_input("Email", value=settings.email or "")
        website = st.text_input("Website", value=settings.website or "")
        address = st.text_area("Address", value=settings.address or "", height=100)
        license_number = st.text_input("License number", value=settings.license_number or "")
        insurance_text = st.text_area("Insurance text", value=settings.insurance_text or "", height=100)
        default_quote_expiration_days = st.number_input(
            "Default quote expiration days",
            min_value=1,
            value=int(settings.default_quote_expiration_days or 30),
            step=1,
        )
        default_payment_terms = st.text_area("Default payment terms", value=settings.default_payment_terms or "", height=120)
        default_warranty_text = st.text_area("Default warranty text", value=settings.default_warranty_text or "", height=120)
        default_footer_text = st.text_area("Default footer text", value=settings.default_footer_text or "", height=100)
        uploaded_logo = st.file_uploader("Company logo", type=["png", "jpg", "jpeg"])
        save_clicked = st.form_submit_button("Save company profile")

    if save_clicked:
        if uploaded_logo is not None:
            settings.logo_path = _save_logo(uploaded_logo)
        settings.company_name = company_name
        settings.phone = phone
        settings.email = email
        settings.website = website
        settings.address = address
        settings.license_number = license_number
        settings.insurance_text = insurance_text
        settings.default_quote_expiration_days = int(default_quote_expiration_days)
        settings.default_payment_terms = default_payment_terms
        settings.default_warranty_text = default_warranty_text
        settings.default_footer_text = default_footer_text
        db.commit()
        st.success("Company profile saved.")
        st.rerun()
finally:
    db.close()
