from __future__ import annotations

from src.constants import DEFAULT_ASSUMPTIONS, DEFAULT_EXCLUSIONS


def _money(value: float) -> str:
    return f"${value:,.2f}"


def generate_proposal_text(customer, project, quote, line_items, change_order_rates) -> str:
    material_lines = [item for item in line_items if item.item_type == "material"]
    labor_lines = list(getattr(quote, "labor_line_items", []))

    scope_lines = "\n".join(
        f"- {item.description}: {item.quantity:g} {item.unit}" for item in line_items
    ) or "- Scope to be finalized."
    material_text = "\n".join(
        f"- {item.description} at {item.quantity:g} {item.unit}" for item in material_lines
    ) or "- No separate material line items listed."
    labor_text = "\n".join(
        f"- {item.task_name} at {item.quantity:g} {item.unit} ({item.final_cost:,.2f})" for item in labor_lines
    ) or "- No separate labor line items listed."
    change_order_text = "\n".join(
        f"- {rate.description}: {_money(rate.unit_price)} per {rate.unit}"
        for rate in change_order_rates
        if rate.trade in {project.trade_scope, "combination"} or project.trade_scope == "combination"
    ) or "- Change orders will be priced in writing before additional work begins."

    return f"""# Proposal: {quote.quote_name}

## Project Summary
Customer: {customer.name}
Project: {project.project_name}
Address: {project.address or customer.address or "TBD"}
Project Type: {project.project_type.replace("_", " ").title()}
Trade Scope: {project.trade_scope.title()}

## Scope of Work
{scope_lines}

## Materials Included
{material_text}

## Labor Included
{labor_text}

## Assumptions
{chr(10).join(f"- {item}" for item in DEFAULT_ASSUMPTIONS)}

## Exclusions
{chr(10).join(f"- {item}" for item in DEFAULT_EXCLUSIONS)}

## Change Order Terms
Change orders will be documented and approved before work proceeds when field conditions, owner requests, or plan revisions change the agreed scope.
{change_order_text}

## Investment
Material Cost: {_money(quote.material_cost)}
Labor Cost: {_money(quote.labor_cost)}
Total Estimated Cost: {_money(quote.total_cost)}
Customer Price: {_money(quote.customer_price)}

## Quote Expiration
This proposal is valid for 30 days from the quote date. Material pricing may be updated after expiration or if supplier costs materially change.
"""
