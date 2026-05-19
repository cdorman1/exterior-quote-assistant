from __future__ import annotations


def rectangle_area(width_ft: float, height_ft: float) -> float:
    return width_ft * height_ft


def triangle_area(base_ft: float, height_ft: float) -> float:
    return base_ft * height_ft / 2


def trapezoid_area(top_width_ft: float, bottom_width_ft: float, height_ft: float) -> float:
    return (top_width_ft + bottom_width_ft) * height_ft / 2


def calculate_opening_area(quantity: float, width_ft: float, height_ft: float) -> float:
    return quantity * width_ft * height_ft


def calculate_total_opening_area(openings: list[dict]) -> float:
    total = 0.0
    for opening in openings:
        width_ft = opening.get("width_ft")
        height_ft = opening.get("height_ft")
        if width_ft is None or height_ft is None:
            continue
        quantity = float(opening.get("quantity") or 1)
        total += calculate_opening_area(quantity, float(width_ft), float(height_ft))
    return round(total, 2)


def calculate_net_wall_area(gross_area: float, opening_area: float = 0) -> float:
    return max(round(gross_area - opening_area, 2), 0)


def siding_squares(square_feet: float) -> float:
    return square_feet / 100


def roofing_squares(square_feet: float) -> float:
    return square_feet / 100


def apply_waste(quantity: float, waste_percent: float) -> float:
    return round(quantity * (1 + waste_percent), 2)


def calculate_area_from_measurement(measurement: dict) -> dict:
    shape = str(measurement.get("shape") or "unknown").lower()
    warnings: list[str] = []

    if shape == "rectangle":
        width_ft = measurement.get("width_ft")
        height_ft = measurement.get("height_ft")
        if width_ft is None or height_ft is None:
            warnings.append("Rectangle measurements require width_ft and height_ft.")
            return {"area_sqft": None, "warnings": warnings}
        return {"area_sqft": rectangle_area(float(width_ft), float(height_ft)), "warnings": warnings}

    if shape == "triangle":
        base_ft = measurement.get("base_ft")
        height_ft = measurement.get("height_ft")
        if base_ft is None or height_ft is None:
            warnings.append("Triangle measurements require base_ft and height_ft.")
            return {"area_sqft": None, "warnings": warnings}
        return {"area_sqft": triangle_area(float(base_ft), float(height_ft)), "warnings": warnings}

    if shape == "trapezoid":
        top_width_ft = measurement.get("top_width_ft")
        bottom_width_ft = measurement.get("bottom_width_ft")
        height_ft = measurement.get("height_ft")
        if top_width_ft is None or bottom_width_ft is None or height_ft is None:
            warnings.append("Trapezoid measurements require top_width_ft, bottom_width_ft, and height_ft.")
            return {"area_sqft": None, "warnings": warnings}
        return {
            "area_sqft": trapezoid_area(float(top_width_ft), float(bottom_width_ft), float(height_ft)),
            "warnings": warnings,
        }

    if shape in {"line", "count"}:
        return {"area_sqft": None, "warnings": warnings}

    warnings.append(f"Unsupported shape: {shape}.")
    return {"area_sqft": None, "warnings": warnings}
