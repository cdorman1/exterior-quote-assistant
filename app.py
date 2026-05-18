import streamlit as st

from src.auth import require_auth
from src.database import init_db

st.set_page_config(page_title="Exterior Quote Assistant", layout="wide")
require_auth()
init_db()

st.markdown(
    """
    <style>
      .hero {
        padding: 1.2rem 1.25rem;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.04), rgba(14, 116, 144, 0.08));
        margin-bottom: 1rem;
      }
      .hero h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.1;
      }
      .hero p {
        margin: 0.4rem 0 0;
        color: rgba(49, 51, 63, 0.8);
      }
      .card-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0 1.25rem;
      }
      .card {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 0.95rem 1rem;
        background: white;
      }
      .card-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(49, 51, 63, 0.65);
      }
      .card-title {
        font-size: 1.15rem;
        font-weight: 650;
        margin-top: 0.35rem;
      }
      .card-body {
        color: rgba(49, 51, 63, 0.75);
        margin-top: 0.35rem;
      }
      .panel {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        background: white;
      }
      .panel-title {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 0.6rem;
      }
      .step {
        display: flex;
        gap: 0.65rem;
        align-items: flex-start;
        margin-bottom: 0.65rem;
      }
      .step-num {
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
      .step-text {
        color: rgba(49, 51, 63, 0.8);
      }
      @media (max-width: 900px) {
        .card-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>Exterior Quote Assistant</h1>
      <p>Contractor quoting dashboard for roofing and siding work.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="card-grid">
      <div class="card">
        <div class="card-label">Workflow</div>
        <div class="card-title">Quote from measured scope</div>
        <div class="card-body">Use the quote builder to price roofing and siding jobs from manual measurements.</div>
      </div>
      <div class="card">
        <div class="card-label">Data</div>
        <div class="card-title">Customers, projects, materials</div>
        <div class="card-body">The sidebar pages hold the operational records that feed quoting and proposal generation.</div>
      </div>
      <div class="card">
        <div class="card-label">Roadmap</div>
        <div class="card-title">Blueprint extraction later</div>
        <div class="card-body">Automated takeoff and blueprint parsing are placeholders for a future release.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1.25, 1])
with left:
    st.markdown(
        """
        <div class="panel">
          <div class="panel-title">Suggested workflow</div>
          <div class="step"><div class="step-num">1</div><div class="step-text">Add or select a customer.</div></div>
          <div class="step"><div class="step-num">2</div><div class="step-text">Create a project and choose new construction or existing construction.</div></div>
          <div class="step"><div class="step-num">3</div><div class="step-text">Review seeded material prices and labor rules.</div></div>
          <div class="step"><div class="step-num">4</div><div class="step-text">Build and save a quote from measured quantities.</div></div>
          <div class="step"><div class="step-num">5</div><div class="step-text">Review generated proposal text in Quotes.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        """
        <div class="panel">
          <div class="panel-title">Where to go next</div>
          <div class="step"><div class="step-num">•</div><div class="step-text">Customers and Projects for your job records.</div></div>
          <div class="step"><div class="step-num">•</div><div class="step-text">Quote Builder for pricing and saving a draft quote.</div></div>
          <div class="step"><div class="step-num">•</div><div class="step-text">Quotes for proposal text and saved output.</div></div>
          <div class="step"><div class="step-num">•</div><div class="step-text">Settings for future company configuration.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
