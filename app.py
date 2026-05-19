import streamlit as st

from src.auth import require_auth
from src.branding import BRAND_NAME, brand_css, render_brand_header, LOGO_PATH
from src.database import init_db

st.set_page_config(page_title=BRAND_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🏗️", layout="wide")
require_auth()
init_db()

st.markdown(brand_css(), unsafe_allow_html=True)

render_brand_header()

left, right = st.columns([1.25, 1])
with left:
    st.markdown('<div class="brand-panel">', unsafe_allow_html=True)
    st.markdown('<div class="brand-panel-title">Suggested workflow</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="brand-step"><div class="brand-step-num">1</div><div class="brand-step-text">Add or select a customer.</div></div>
        <div class="brand-step"><div class="brand-step-num">2</div><div class="brand-step-text">Create a project and choose new construction or existing construction.</div></div>
        <div class="brand-step"><div class="brand-step-num">3</div><div class="brand-step-text">Review seeded material prices and labor rules.</div></div>
        <div class="brand-step"><div class="brand-step-num">4</div><div class="brand-step-text">Build and save a quote from measured quantities.</div></div>
        <div class="brand-step"><div class="brand-step-num">5</div><div class="brand-step-text">Review generated proposal text in Quotes.</div></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="brand-panel">', unsafe_allow_html=True)
    st.markdown('<div class="brand-panel-title">Where to go next</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="brand-step"><div class="brand-step-num">•</div><div class="brand-step-text">Customers and Projects for your job records.</div></div>
        <div class="brand-step"><div class="brand-step-num">•</div><div class="brand-step-text">Quote Builder for pricing and saving a draft quote.</div></div>
        <div class="brand-step"><div class="brand-step-num">•</div><div class="brand-step-text">Quotes for proposal text and saved output.</div></div>
        <div class="brand-step"><div class="brand-step-num">•</div><div class="brand-step-text">Company Settings for future company configuration.</div></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
