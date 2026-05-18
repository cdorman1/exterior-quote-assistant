from __future__ import annotations


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
