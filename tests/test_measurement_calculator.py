from __future__ import annotations

import pytest

from src.measurement_calculator import (
    apply_waste,
    calculate_area_from_measurement,
    calculate_net_wall_area,
    calculate_opening_area,
    calculate_total_opening_area,
    rectangle_area,
    roofing_squares,
    siding_squares,
    trapezoid_area,
    triangle_area,
)


def test_rectangle_area():
    assert rectangle_area(10, 12) == 120


def test_triangle_area():
    assert triangle_area(10, 12) == 60


def test_trapezoid_area():
    assert trapezoid_area(8, 12, 10) == 100


def test_calculate_opening_area():
    assert calculate_opening_area(2, 3, 4) == 24


def test_calculate_total_opening_area():
    assert calculate_total_opening_area(
        [
            {"quantity": 2, "width_ft": 3, "height_ft": 4},
            {"quantity": 1, "width_ft": 5, "height_ft": 6},
            {"quantity": 1, "width_ft": None, "height_ft": 4},
        ]
    ) == 54


def test_calculate_net_wall_area():
    assert calculate_net_wall_area(500, 75) == 425


def test_calculate_net_wall_area_never_negative():
    assert calculate_net_wall_area(50, 75) == 0


def test_siding_squares():
    assert siding_squares(250) == 2.5


def test_roofing_squares():
    assert roofing_squares(250) == 2.5


def test_apply_waste():
    assert apply_waste(100, 0.1) == 110


def test_calculate_area_from_measurement_rectangle():
    result = calculate_area_from_measurement({"shape": "rectangle", "width_ft": 10, "height_ft": 12})
    assert result["area_sqft"] == 120
    assert result["warnings"] == []


def test_calculate_area_from_measurement_triangle():
    result = calculate_area_from_measurement({"shape": "triangle", "base_ft": 10, "height_ft": 12})
    assert result["area_sqft"] == 60
    assert result["warnings"] == []


def test_calculate_area_from_measurement_trapezoid():
    result = calculate_area_from_measurement(
        {"shape": "trapezoid", "top_width_ft": 8, "bottom_width_ft": 12, "height_ft": 10}
    )
    assert result["area_sqft"] == 100
    assert result["warnings"] == []


def test_calculate_area_from_measurement_missing_dimensions():
    result = calculate_area_from_measurement({"shape": "rectangle", "width_ft": 10})
    assert result["area_sqft"] is None
    assert result["warnings"]
