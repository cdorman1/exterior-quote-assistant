from __future__ import annotations

from pathlib import Path

import streamlit as st


BRAND_NAME = "Quote Assistant"
BRAND_TAGLINE = "Contractor quoting dashboard for roofing and siding work."
LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "ek_view_construction.png"


def brand_css() -> str:
    return """
    <style>
      .brand-hero {
        padding: 1rem 1.1rem;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 12px;
        background: white;
        margin-bottom: 1rem;
      }
      .brand-hero h1 {
        margin: 0;
        font-size: 1.8rem;
        line-height: 1.1;
      }
      .brand-hero p {
        margin: 0.35rem 0 0;
        color: rgba(49, 51, 63, 0.78);
      }
      .brand-card {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 0.95rem 1rem;
        background: white;
      }
      .brand-card-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(49, 51, 63, 0.65);
      }
      .brand-card-title {
        font-size: 1.1rem;
        font-weight: 650;
        margin-top: 0.35rem;
      }
      .brand-card-body {
        color: rgba(49, 51, 63, 0.75);
        margin-top: 0.35rem;
      }
      .brand-panel {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        background: white;
      }
      .brand-panel-title {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 0.6rem;
      }
      .brand-step {
        display: flex;
        gap: 0.65rem;
        align-items: flex-start;
        margin-bottom: 0.65rem;
      }
      .brand-step-num {
        width: 1.4rem;
        height: 1.4rem;
        border-radius: 999px;
        background: rgba(14, 116, 144, 0.12);
        color: rgb(15, 118, 110);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.78rem;
        font-weight: 700;
        flex: 0 0 auto;
      }
      .brand-step-text {
        color: rgba(49, 51, 63, 0.8);
      }
      .brand-section {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        background: white;
      }
      .brand-section-title {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 0.6rem;
      }
    </style>
    """


def render_brand_header(title: str = BRAND_NAME, subtitle: str = BRAND_TAGLINE) -> None:
    logo_path = str(LOGO_PATH) if LOGO_PATH.exists() else None
    cols = st.columns([0.8, 3.2])
    with cols[0]:
        if logo_path:
            st.image(logo_path, use_container_width=True)
    with cols[1]:
        st.title(title)
        st.caption(subtitle)
