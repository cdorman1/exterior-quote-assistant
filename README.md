# Exterior Quote Assistant

Status: public source repository for a private/client-facing quoting app. Do not
commit live OpenAI keys, auth hashes, `.env` files, uploaded blueprints/images,
generated proposals, customer records, SQLite databases, logs, or deployment
secrets.

Exterior Quote Assistant is an MVP contractor quoting dashboard for roofing and siding contractors. It supports new construction jobs quoted from blueprint measurements entered manually and existing construction jobs quoted from field measurements.

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

Run tests with:

```bash
python -m pytest
```

## Authentication

The app now requires a username and password before any page renders.

Set these in `.env`:

```bash
APP_AUTH_USERNAME=admin
APP_AUTH_PASSWORD_HASH=pbkdf2_sha256$260000$...
```

The VPS service reads `/opt/exterior-quote-assistant/.env` directly through systemd, so keep the credentials there and restart the service after changes.

Generate the password hash locally with:

```bash
python -m src.auth your-plaintext-password
```

The command prints a hash you can paste into `.env`.

Never commit generated password hashes for real deployments. Keep production
credentials in the VPS-local `.env` file or another approved secret store.

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

The app service listens on `0.0.0.0:8501`. Traefik routes the app at `https://sentinelforge.tech/quote-system` and strips that prefix before forwarding to Streamlit.

To point the domain at the VPS, add DNS records at your domain provider:

```text
A     sentinelforge.tech      <your VPS public IPv4>
```

If you want only one endpoint, use just the root domain and the `/quote-system` path.

## Labor Estimating Workflow

The user selects a project, trade, measurement quantity, labor method, difficulty, and optional complexity conditions.

The system loads default labor tasks for the selected trade and project type.

The system calculates labor line items and a labor summary from the selected method.

Manual labor overrides are allowed, but an override reason should be provided to avoid review warnings.

The labor breakdown is saved with the quote.

## Professional Proposal Generation

Saved quotes can be converted into customer facing proposals that look more like a finished contractor estimate package than an internal worksheet.

The proposal includes company logo, company information, customer information, project details, scope of work, material summary, labor summary, assumptions, exclusions, change order terms, payment terms, warranty language, total investment, and approval section.

Internal estimate details such as margin, raw profit, raw labor rates, and internal markup calculations are not shown on customer proposals by default.

## Company Settings

The Settings page allows users to configure company name, contact information, logo, payment terms, warranty language, license information, insurance text, and footer text.

## Blueprint Upload and Assisted Takeoff

The app supports uploading blueprint PDF files and attaching them to projects.

It extracts basic PDF text with PyMuPDF and attempts to detect sheet names, sheet numbers, sheet types, and scale text.

This version does not automatically calculate measurements from drawings.

The estimator must manually enter takeoff measurements and mark them approved.

Only approved takeoff measurements can be used in quote calculations.

## OpenAI Vision Measurement Extraction

The app can use OpenAI vision to extract visible typed or handwritten measurements from uploaded images.

The model returns structured measurements.

The app performs area calculations deterministically.

The image extraction page is a reference aid. It shows the extracted measurements, but final quantities are entered in Quote Builder.

Use the extracted values as a guide when completing the quote.

Set these environment variables before using image extraction:

```bash
OPENAI_API_KEY=
OPENAI_VISION_MODEL=gpt-5.5
```

The `OPENAI_API_KEY` value must remain local to the deployment environment.

## Development Note

During early development, if database models change, delete `data/exterior_quote_assistant.db` and rerun:

```bash
python -m src.seed_data
```

Before opening a pull request, run the test suite and scan the diff for accidental
credentials or private customer/project data.

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
    proposal_service.py
    pdf_service.py
    measurement_calculator.py
    openai_vision_service.py
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
    99_company_settings.py
    10_blueprints.py
    11_takeoff_measurements.py
    12_proposals.py
    13_image_measurement_extraction.py
  tests/
    test_pricing_engine.py
    test_blueprint_service.py
    test_proposal_service.py
    test_pdf_service.py
    test_measurement_calculator.py
    test_openai_vision_service.py
```

## MVP Scope

- Customer and project management
- Project type support for `new_construction` and `existing_construction`
- Trade scope support for roofing, siding, and combination jobs
- Seeded material prices, labor tasks, waste rules, complexity rules, and change order rates
- Manual measured quantity entry from blueprints or field measurements
- Labor estimating by unit-based, crew-day, hourly, and subcontractor methods
- Material cost, labor cost, tax, total cost, and gross-margin customer price calculations
- Saved quotes with material and labor line items
- Generated proposal text with scope, assumptions, exclusions, investment, and change order terms
- Company settings and branded customer-facing proposal PDFs

## Future Features

- PDF scale calibration
- Interactive tracing
- Roof area takeoff
- Siding elevation takeoff
- AI suggested measurements
- OCR for scanned plans
- DXF/CAD parsing
- Plan revision comparison
- Multi-line quote builder for complex assemblies
- Supplier price imports and historical pricing
- Company branding and editable proposal templates
- User accounts and permissions
- Quote versioning and approval tracking
