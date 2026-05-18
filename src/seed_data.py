from __future__ import annotations

from datetime import date

from src.database import SessionLocal, init_db
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
    ("Roof tear off per square", "roofing", "square", 85, 750),
    ("Roof install per square", "roofing", "square", 175, 1200),
    ("Roof decking replacement per sheet", "roofing", "sheet", 55, 250),
    ("Siding tear off per square", "siding", "square", 70, 600),
    ("Siding install per square", "siding", "square", 190, 1300),
    ("Soffit install per linear foot", "siding", "linear foot", 7.5, 350),
    ("Fascia install per linear foot", "siding", "linear foot", 6.5, 350),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
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

        for name, trade, unit, cost, minimum in LABOR_TASKS:
            db.add(
                LaborTask(
                    name=name,
                    trade=trade,
                    unit=unit,
                    base_labor_cost=cost,
                    minimum_charge=minimum,
                    active=True,
                )
            )

        for trade in ["roofing", "siding"]:
            db.add_all(
                [
                    WasteRule(trade=trade, condition_name="Standard", waste_percent=0.10),
                    WasteRule(trade=trade, condition_name="Simple layout", waste_percent=0.05),
                    WasteRule(trade=trade, condition_name="Complex layout", waste_percent=0.15),
                    ComplexityRule(trade=trade, condition_name="Standard", multiplier=1.0),
                    ComplexityRule(trade=trade, condition_name="Difficult access", multiplier=1.15),
                    ComplexityRule(trade=trade, condition_name="High complexity", multiplier=1.30),
                    ChangeOrderRate(
                        trade=trade,
                        description=f"{trade.title()} additional work",
                        unit="hour",
                        unit_price=95,
                        notes="Default hourly change order rate",
                    ),
                ]
            )
        db.commit()
        print("Database initialized with sample exterior quoting data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
