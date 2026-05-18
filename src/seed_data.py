from __future__ import annotations

from datetime import date

from sqlalchemy import inspect

from src.constants import LABOR_CONDITION_MULTIPLIERS, LABOR_DIFFICULTY_MULTIPLIERS
from src.database import Base, SessionLocal, engine, init_db
from src.models import (
    ChangeOrderRate,
    ComplexityRule,
    Customer,
    LaborTask,
    Material,
    MaterialPrice,
    Project,
    WasteRule,
)

MATERIALS = [
    ("Architectural shingles", "roofing", "roof covering", "square", 0.10, 145),
    ("Synthetic underlayment", "roofing", "underlayment", "roll", 0.10, 92),
    ("Ice and water shield", "roofing", "underlayment", "roll", 0.08, 118),
    ("Starter shingles", "roofing", "accessory", "bundle", 0.08, 42),
    ("Ridge cap", "roofing", "accessory", "bundle", 0.08, 58),
    ("Drip edge", "roofing", "metal", "linear foot", 0.05, 1.85),
    ("Ridge vent", "roofing", "ventilation", "linear foot", 0.05, 5.25),
    ("Flashing", "roofing", "metal", "linear foot", 0.10, 4.75),
    ("Pipe boot", "roofing", "accessory", "each", 0.05, 18),
    ("Roof decking sheet", "roofing", "decking", "sheet", 0.05, 42),
    ("Vinyl siding", "siding", "siding", "square", 0.10, 118),
    ("House wrap", "siding", "weather barrier", "roll", 0.08, 96),
    ("Foam board", "siding", "insulation", "sheet", 0.08, 14),
    ("Starter strip", "siding", "accessory", "linear foot", 0.05, 0.85),
    ("J channel", "siding", "accessory", "linear foot", 0.08, 1.2),
    ("Outside corner post", "siding", "accessory", "each", 0.05, 16),
    ("Inside corner post", "siding", "accessory", "each", 0.05, 14),
    ("Soffit", "siding", "soffit", "linear foot", 0.08, 4.6),
    ("Fascia", "siding", "fascia", "linear foot", 0.08, 3.75),
    ("Trim coil", "siding", "metal", "roll", 0.08, 122),
]

LABOR_TASKS = [
    ("Roof tear off", "roofing", "square", 90, 750, 1.0, "existing_construction", "Existing construction tear off"),
    ("Roof install architectural shingles", "roofing", "square", 125, 1000, 1.0, "both", "Primary roofing install"),
    ("Roof decking replacement", "roofing", "each", 65, 0, 1.0, "both", "Per sheet replacement"),
    ("Install ridge vent", "roofing", "linear_foot", 8, 0, 1.0, "both", "Ventilation accessory labor"),
    ("Flashing labor", "roofing", "linear_foot", 12, 0, 1.0, "both", "Flashing and penetration detailing"),
    ("Siding tear off", "siding", "square", 85, 750, 1.0, "existing_construction", "Existing siding removal"),
    ("Install vinyl siding", "siding", "square", 300, 2500, 1.0, "both", "Primary siding install"),
    ("Install house wrap", "siding", "square", 45, 0, 1.0, "both", "Weather barrier labor"),
    ("Install soffit", "siding", "linear_foot", 8, 0, 1.0, "both", "Soffit install labor"),
    ("Install fascia", "siding", "linear_foot", 9, 0, 1.0, "both", "Fascia install labor"),
    ("Trim and corner package", "siding", "allowance", 1200, 0, 1.0, "both", "Allowance for trim package"),
]

COMPLEXITY_RULES = [
    ("roofing", "simple", LABOR_DIFFICULTY_MULTIPLIERS["simple"]),
    ("roofing", "moderate", LABOR_DIFFICULTY_MULTIPLIERS["moderate"]),
    ("roofing", "difficult", LABOR_DIFFICULTY_MULTIPLIERS["difficult"]),
    ("roofing", "very_difficult", LABOR_DIFFICULTY_MULTIPLIERS["very_difficult"]),
    *[("roofing", name, multiplier) for name, multiplier in LABOR_CONDITION_MULTIPLIERS["roofing"].items()],
    ("siding", "simple", LABOR_DIFFICULTY_MULTIPLIERS["simple"]),
    ("siding", "moderate", LABOR_DIFFICULTY_MULTIPLIERS["moderate"]),
    ("siding", "difficult", LABOR_DIFFICULTY_MULTIPLIERS["difficult"]),
    ("siding", "very_difficult", LABOR_DIFFICULTY_MULTIPLIERS["very_difficult"]),
    *[("siding", name, multiplier) for name, multiplier in LABOR_CONDITION_MULTIPLIERS["siding"].items()],
]

CHANGE_ORDER_RATES = {
    "roofing": 95,
    "siding": 90,
}

REQUIRED_TABLES = {"labor_tasks", "quote_labor_line_items"}
REQUIRED_QUOTE_COLUMNS = {
    "id",
    "project_id",
    "quote_name",
    "status",
    "target_margin",
    "tax_rate",
    "permit_cost",
    "disposal_cost",
    "equipment_cost",
    "overhead_cost",
    "material_cost",
    "labor_cost",
    "total_cost",
    "customer_price",
    "notes",
    "created_at",
}
REQUIRED_LABOR_TASK_COLUMNS = {
    "id",
    "name",
    "trade",
    "unit",
    "base_labor_cost",
    "minimum_charge",
    "default_multiplier",
    "applies_to_project_type",
    "active",
    "notes",
}
ALLOWED_TRADES = {"roofing", "siding"}
REQUIRED_QUOTE_LABOR_COLUMNS = {
    "id",
    "quote_id",
    "trade",
    "labor_method",
    "task_name",
    "quantity",
    "unit",
    "base_rate",
    "complexity_multiplier",
    "minimum_charge",
    "calculated_cost",
    "manual_override_cost",
    "final_cost",
    "override_reason",
    "notes",
    "created_at",
}


def _database_needs_reset() -> bool:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not REQUIRED_TABLES.union({"blueprint_files", "blueprint_sheets", "takeoff_measurements"}).issubset(existing_tables):
        return True
    labor_columns = {column["name"] for column in inspector.get_columns("labor_tasks")}
    quote_labor_columns = {column["name"] for column in inspector.get_columns("quote_labor_line_items")}
    quote_columns = {column["name"] for column in inspector.get_columns("quotes")}
    if (
        not REQUIRED_LABOR_TASK_COLUMNS.issubset(labor_columns)
        or not REQUIRED_QUOTE_LABOR_COLUMNS.issubset(quote_labor_columns)
        or not REQUIRED_QUOTE_COLUMNS.issubset(quote_columns)
    ):
        return True

    db = SessionLocal()
    try:
        return (
            db.query(Material).filter(~Material.trade.in_(sorted(ALLOWED_TRADES))).first() is not None
            or db.query(LaborTask).filter(~LaborTask.trade.in_(sorted(ALLOWED_TRADES))).first() is not None
            or db.query(ComplexityRule).filter(~ComplexityRule.trade.in_(sorted(ALLOWED_TRADES))).first() is not None
            or db.query(ChangeOrderRate).filter(~ChangeOrderRate.trade.in_(sorted(ALLOWED_TRADES))).first() is not None
        )
    finally:
        db.close()


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if _database_needs_reset():
            db.close()
            Base.metadata.drop_all(bind=engine)
            init_db()
            db = SessionLocal()
        if db.query(Material).first():
            print("Seed data already exists.")
            return

        customer = Customer(
            name="Jordan Smith",
            company_name="Smith Development",
            phone="555-0100",
            email="jordan@example.com",
            address="100 Main St, Springfield",
            notes="Sample customer",
        )
        db.add(customer)
        db.flush()
        db.add(
            Project(
                customer_id=customer.id,
                project_name="Oak Ridge Exterior Package",
                project_type="new_construction",
                trade_scope="combination",
                address="2400 Oak Ridge Dr, Springfield",
                status="estimating",
                notes="Blueprint measurements entered manually for MVP.",
            )
        )

        for name, trade, category, unit, waste, cost in MATERIALS:
            material = Material(
                name=name,
                trade=trade,
                category=category,
                unit=unit,
                default_waste_factor=waste,
                active=True,
            )
            db.add(material)
            db.flush()
            db.add(
                MaterialPrice(
                    material_id=material.id,
                    supplier="Default Supplier",
                    unit_cost=cost,
                    effective_date=date.today(),
                    notes="Initial sample price",
                )
            )

        for name, trade, unit, cost, minimum, default_multiplier, applies_to_project_type, notes in LABOR_TASKS:
            db.add(
                LaborTask(
                    name=name,
                    trade=trade,
                    unit=unit,
                    base_labor_cost=cost,
                    minimum_charge=minimum,
                    default_multiplier=default_multiplier,
                    applies_to_project_type=applies_to_project_type,
                    active=True,
                    notes=notes,
                )
            )

        for trade in ["roofing", "siding"]:
            db.add_all(
                [
                    WasteRule(trade=trade, condition_name="Standard", waste_percent=0.10),
                    WasteRule(trade=trade, condition_name="Simple layout", waste_percent=0.05),
                    WasteRule(trade=trade, condition_name="Complex layout", waste_percent=0.15),
                ]
            )

        for trade, condition_name, multiplier in COMPLEXITY_RULES:
            db.add(ComplexityRule(trade=trade, condition_name=condition_name, multiplier=multiplier))

        for trade, unit_price in CHANGE_ORDER_RATES.items():
            db.add(
                ChangeOrderRate(
                    trade=trade,
                    description=f"{trade.title()} additional work",
                    unit="hour",
                    unit_price=unit_price,
                    notes="Default hourly change order rate",
                )
            )

        db.commit()
        print("Database initialized with sample exterior quoting data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
