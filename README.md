# Exterior Quote Assistant

Exterior Quote Assistant is an MVP contractor quoting dashboard for roofing, siding, and masonry contractors. It supports new construction jobs quoted from blueprint measurements entered manually and existing construction jobs quoted from field measurements.

Version 1 intentionally does not automate blueprint measurement extraction. The scaffold focuses on the pricing engine, database models, seed data, Streamlit dashboard, and a basic quote-to-proposal workflow.

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.seed_data
streamlit run app.py
```

The app uses SQLite by default at `data/exterior_quote_assistant.db`. Copy `.env.example` to `.env` if you want to override defaults.

## Hostinger VPS Deployment

The `deploy/` directory includes a basic Ubuntu VPS deployment setup using systemd and Traefik.

On the VPS, run:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/cdorman1/exterior-quote-assistant.git /tmp/exterior-quote-assistant
sudo bash /tmp/exterior-quote-assistant/deploy/hostinger_setup.sh
```

After deployment:

```bash
sudo systemctl status exterior-quote-assistant
sudo journalctl -u exterior-quote-assistant -f
```

The app service listens on `0.0.0.0:8501`. Traefik should route `https://srv1674962.hstgr.cloud` to that service using the dynamic config in `deploy/traefik-exterior-quote-assistant.yml`.

## Project Structure

```text
exterior_quote_assistant/
  app.py
  requirements.txt
  .env.example
  README.md
  data/
    exterior_quote_assistant.db
    sample_material_prices.csv
  src/
    database.py
    models.py
    schemas.py
    seed_data.py
    pricing_engine.py
    proposal_generator.py
    csv_importer.py
    constants.py
  pages/
    01_dashboard.py
    02_customers.py
    03_projects.py
    04_quote_builder.py
    05_materials.py
    06_labor_rules.py
    07_quotes.py
    08_change_orders.py
    09_settings.py
  tests/
    test_pricing_engine.py
```

## MVP Scope

- Customer and project management
- Project type support for `new_construction` and `existing_construction`
- Trade scope support for roofing, siding, masonry, and combination jobs
- Seeded material prices, labor tasks, waste rules, complexity rules, and change order rates
- Manual measured quantity entry from blueprints or field measurements
- Material cost, labor cost, tax, total cost, and gross-margin customer price calculations
- Saved quotes with line items
- Generated proposal text with scope, assumptions, exclusions, investment, and change order terms

## Future Features

- Blueprint upload and measurement extraction
- OCR, CAD, or takeoff tool integrations
- Multi-line quote builder for complex assemblies
- Supplier price imports and historical pricing
- Company branding and editable proposal templates
- User accounts and permissions
- PDF proposal export
- Quote versioning and approval tracking
