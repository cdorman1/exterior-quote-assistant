import pytest

from src.pricing_engine import (
    RectangularOpening,
    RectangularWall,
    TriangularGable,
    calculate_customer_price,
    calculate_crew_day_labor,
    calculate_final_complexity_multiplier,
    calculate_hourly_labor,
    calculate_labor_cost,
    calculate_labor_summary,
    calculate_material_cost,
    calculate_quote_totals,
    calculate_subcontractor_labor,
    calculate_vinyl_siding_takeoff,
)


def test_calculate_material_cost_applies_waste_factor():
    assert calculate_material_cost(10, 100, 0.10) == 1100


def test_calculate_labor_cost_applies_complexity_and_minimum():
    result = calculate_labor_cost(5, 100, 1.25, minimum_charge=700)
    assert result["calculated_cost"] == 625
    assert result["final_cost"] == 700
    assert result["minimum_charge_applied"] is True
    assert result["manual_override_applied"] is False


def test_calculate_labor_cost_manual_override_applied():
    result = calculate_labor_cost(10, 100, 1.25, minimum_charge=700, manual_override_cost=800)
    assert result["calculated_cost"] == 1250
    assert result["final_cost"] == 800
    assert result["minimum_charge_applied"] is False
    assert result["manual_override_applied"] is True


def test_calculate_crew_day_labor():
    result = calculate_crew_day_labor(1200, 2, 1.15)
    assert result["calculated_cost"] == 2760
    assert result["final_cost"] == 2760


def test_calculate_hourly_labor():
    result = calculate_hourly_labor(8, 85, 1.3)
    assert result["calculated_cost"] == 884
    assert result["final_cost"] == 884


def test_calculate_subcontractor_labor():
    result = calculate_subcontractor_labor(5000, 0.10)
    assert result["calculated_cost"] == 5500
    assert result["final_cost"] == 5500


def test_calculate_final_complexity_multiplier():
    multiplier = calculate_final_complexity_multiplier(1.15, [1.15, 1.10])
    assert multiplier == pytest.approx(1.45475)


def test_calculate_labor_summary_rolls_up_totals():
    summary = calculate_labor_summary(
        [
            {
                "quantity": 5,
                "base_rate": 100,
                "calculated_cost": 625,
                "final_cost": 700,
                "manual_override_applied": False,
                "minimum_charge_applied": True,
            },
            {
                "quantity": 2,
                "base_rate": 300,
                "calculated_cost": 600,
                "final_cost": 550,
                "manual_override_applied": True,
                "minimum_charge_applied": False,
            },
        ]
    )

    assert summary["base_labor_total"] == 1100
    assert summary["adjusted_labor_total"] == 1225
    assert summary["manual_override_total"] == 550
    assert summary["minimum_charge_adjustment_total"] == 75
    assert summary["final_labor_total"] == 1250


def test_calculate_customer_price_uses_gross_margin_math():
    assert calculate_customer_price(6000, 0.40) == 10000


def test_calculate_customer_price_rejects_invalid_margin():
    with pytest.raises(ValueError):
        calculate_customer_price(1000, 1)


def test_calculate_quote_totals_rolls_up_costs_and_labor():
    result = calculate_quote_totals(
        line_items=[
            {"item_type": "material", "line_cost": 1000},
        ],
        permit_cost=100,
        disposal_cost=50,
        equipment_cost=25,
        overhead_cost=25,
        target_margin=0.40,
        tax_rate=0.10,
        labor_line_items=[
            {
                "quantity": 5,
                "base_rate": 100,
                "calculated_cost": 625,
                "final_cost": 700,
                "manual_override_applied": False,
                "minimum_charge_applied": True,
            }
        ],
    )

    assert result["material_cost"] == 1000
    assert result["labor_cost"] == 700
    assert result["tax_amount"] == 190
    assert result["total_cost"] == 2090
    assert result["customer_price"] == 3483.33


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
