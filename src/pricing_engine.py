from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Sequence


@dataclass(frozen=True)
class RectangularWall:
    length_ft: float
    height_ft: float


@dataclass(frozen=True)
class TriangularGable:
    base_ft: float
    height_ft: float


@dataclass(frozen=True)
class RectangularOpening:
    width_ft: float
    height_ft: float


@dataclass(frozen=True)
class VinylSidingTakeoffResult:
    gross_square_feet: float
    net_square_feet: float
    waste_square_feet: float
    total_square_feet: float
    siding_squares: int


def _rectangular_area(length_ft: float, height_ft: float) -> float:
    return length_ft * height_ft


def _triangular_area(base_ft: float, height_ft: float) -> float:
    return 0.5 * base_ft * height_ft


def calculate_vinyl_siding_takeoff(
    walls: Sequence[RectangularWall] | None = None,
    gables: Sequence[TriangularGable] | None = None,
    openings: Sequence[RectangularOpening] | None = None,
    waste_percent: float = 0.10,
) -> VinylSidingTakeoffResult:
    """
    Calculate vinyl siding takeoff in square feet and 100-sq-ft squares.

    Walls are rectangles, gables are triangles, and openings are rectangular
    deductions. Waste is applied after deductions. One siding square equals
    100 square feet, and squares are rounded up to the next whole square.
    """
    if waste_percent < 0:
        raise ValueError("waste_percent must be greater than or equal to 0")

    walls = walls or []
    gables = gables or []
    openings = openings or []

    gross_square_feet = round(
        sum(_rectangular_area(wall.length_ft, wall.height_ft) for wall in walls)
        + sum(_triangular_area(gable.base_ft, gable.height_ft) for gable in gables),
        2,
    )
    opening_square_feet = round(
        sum(_rectangular_area(opening.width_ft, opening.height_ft) for opening in openings),
        2,
    )
    net_square_feet = round(max(gross_square_feet - opening_square_feet, 0), 2)
    waste_square_feet = round(net_square_feet * waste_percent, 2)
    total_square_feet = round(net_square_feet + waste_square_feet, 2)
    siding_squares = ceil(total_square_feet / 100) if total_square_feet > 0 else 0
    return VinylSidingTakeoffResult(
        gross_square_feet=gross_square_feet,
        net_square_feet=net_square_feet,
        waste_square_feet=waste_square_feet,
        total_square_feet=total_square_feet,
        siding_squares=siding_squares,
    )


def calculate_material_cost(quantity: float, unit_cost: float, waste_factor: float) -> float:
    return round(quantity * unit_cost * (1 + waste_factor), 2)


def calculate_labor_cost(
    quantity: float,
    labor_unit_cost: float,
    complexity_multiplier: float,
    minimum_charge: float = 0,
) -> float:
    calculated = quantity * labor_unit_cost * complexity_multiplier
    return round(max(calculated, minimum_charge), 2)


def calculate_customer_price(total_cost: float, target_margin: float) -> float:
    if target_margin < 0 or target_margin >= 1:
        raise ValueError("target_margin must be greater than or equal to 0 and less than 1")
    return round(total_cost / (1 - target_margin), 2)


def calculate_quote_totals(
    line_items: list[dict],
    permit_cost: float,
    disposal_cost: float,
    equipment_cost: float,
    overhead_cost: float,
    target_margin: float,
    tax_rate: float,
) -> dict:
    material_cost = round(
        sum(item["line_cost"] for item in line_items if item.get("item_type") == "material"),
        2,
    )
    labor_cost = round(
        sum(item["line_cost"] for item in line_items if item.get("item_type") == "labor"),
        2,
    )
    subtotal_cost = material_cost + labor_cost + permit_cost + disposal_cost + equipment_cost + overhead_cost
    tax_amount = round(subtotal_cost * tax_rate, 2)
    total_cost = round(subtotal_cost + tax_amount, 2)
    customer_price = calculate_customer_price(total_cost, target_margin)
    return {
        "material_cost": material_cost,
        "labor_cost": labor_cost,
        "tax_amount": tax_amount,
        "total_cost": total_cost,
        "customer_price": customer_price,
    }
