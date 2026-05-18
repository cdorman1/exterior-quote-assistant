import pytest

from src.pricing_engine import (
    calculate_customer_price,
    calculate_labor_cost,
    calculate_material_cost,
    calculate_quote_totals,
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
