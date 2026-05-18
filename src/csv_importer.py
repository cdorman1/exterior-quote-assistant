from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.models import Material, MaterialPrice


def import_material_prices(csv_path: str | Path, db) -> int:
    df = pd.read_csv(csv_path)
    imported = 0
    for row in df.to_dict(orient="records"):
        material = db.query(Material).filter(Material.name == row["material_name"]).first()
        if not material:
            material = Material(
                name=row["material_name"],
                trade=row["trade"],
                category=row.get("category", "general"),
                unit=row["unit"],
                default_waste_factor=float(row.get("default_waste_factor", 0.10)),
                active=True,
            )
            db.add(material)
            db.flush()
        db.add(
            MaterialPrice(
                material_id=material.id,
                supplier=row.get("supplier", "Default Supplier"),
                unit_cost=float(row["unit_cost"]),
                effective_date=date.fromisoformat(str(row.get("effective_date", date.today()))),
                notes=row.get("notes"),
            )
        )
        imported += 1
    db.commit()
    return imported
