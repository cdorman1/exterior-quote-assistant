import streamlit as st

from src.auth import require_auth

require_auth()
st.title("Settings")
st.text_input("Company name", placeholder="Future company profile setting")
st.text_area("Default proposal terms", placeholder="Future reusable terms and conditions")
st.file_uploader("Blueprint upload placeholder", type=["pdf", "png", "jpg", "jpeg", "dwg"], disabled=True)
st.info("Future versions can add company branding, default margins, tax profiles, blueprint uploads, and measurement extraction settings.")
