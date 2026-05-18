import pytest

from src.pricing_engine import (
    calculate_customer_price,
    calculate_labor_cost,
    calculate_material_cost,
    calculate_quote_totals,
    calculate_vinyl_siding_takeoff,
    RectangularOpening,
    RectangularWall,
    TriangularGable,
)


def test_calculate_material_cost_applies_waste_factor():
    assert calculate_material_cost(10, 100, 0.10) == 1100


def test_calculate_labor_cost_applies_complexity_and_minimum():
    assert calculate_labor_cost(5, 100, 1.25, minimum_charge=700) == 700
    assert calculate_labor_cost(10, 100, 1.25, minimum_charge=700) == 1250


def test_calculate_customer_price_uses_gross_margin_math():
    assert calculate_customer_price(6000, 0.40) == 10000


def test_calculate_customer_price_rejects_invalid_margin():
    with pytest.raises(ValueError):
        calculate_customer_price(1000, 1)


def test_calculate_quote_totals_rolls_up_costs_and_tax():
    result = calculate_quote_totals(
        line_items=[
            {"item_type": "material", "line_cost": 1000},
            {"item_type": "labor", "line_cost": 500},
        ],
        permit_cost=100,
        disposal_cost=50,
        equipment_cost=25,
        overhead_cost=25,
        target_margin=0.40,
        tax_rate=0.10,
    )

    assert result["material_cost"] == 1000
    assert result["labor_cost"] == 500
    assert result["tax_amount"] == 170
    assert result["total_cost"] == 1870
    assert result["customer_price"] == 3116.67


def test_calculate_vinyl_siding_takeoff_calculates_area_waste_and_squares():
    result = calculate_vinyl_siding_takeoff(
        walls=[
            RectangularWall(length_ft=20, height_ft=10),
            RectangularWall(length_ft=10, height_ft=10),
        ],
        gables=[
            TriangularGable(base_ft=20, height_ft=5),
        ],
        openings=[
            RectangularOpening(width_ft=3, height_ft=7),
            RectangularOpening(width_ft=4, height_ft=5),
        ],
    )

    assert result.gross_square_feet == 350.0
    assert result.net_square_feet == 309.0
    assert result.waste_square_feet == 30.9
    assert result.total_square_feet == 339.9
    assert result.siding_squares == 4


def test_calculate_vinyl_siding_takeoff_rejects_negative_waste():
    with pytest.raises(ValueError):
        calculate_vinyl_siding_takeoff(waste_percent=-0.01)
