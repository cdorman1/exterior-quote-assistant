import streamlit as st

from src.database import init_db

st.set_page_config(page_title="Exterior Quote Assistant", layout="wide")
init_db()

st.title("Exterior Quote Assistant")
st.write(
    "MVP contractor quoting dashboard for roofing, siding, and masonry work. "
    "Use the sidebar pages to manage customers, projects, materials, quote workflow, and proposal text."
)

st.info(
    "Blueprint upload and automated measurement extraction are future placeholders. "
    "For version 1, enter blueprint or field measurements manually in Quote Builder."
)

st.subheader("Suggested workflow")
st.markdown(
    "1. Add or select a customer.\n"
    "2. Create a project and choose new construction or existing construction.\n"
    "3. Review seeded material prices and labor rules.\n"
    "4. Build and save a quote from measured quantities.\n"
    "5. Review generated proposal text in Quotes."
)
