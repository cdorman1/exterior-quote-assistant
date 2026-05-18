from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str
    company_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerRead(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ProjectCreate(BaseModel):
    customer_id: int
    project_name: str
    project_type: str
    trade_scope: str
    address: str | None = None
    status: str = "lead"
    notes: str | None = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    trade: str
    category: str
    unit: str
    default_waste_factor: float
    active: bool


class MaterialPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    supplier: str
    unit_cost: float
    effective_date: date
    expiration_date: date | None = None
    notes: str | None = None


class QuoteLineItemInput(BaseModel):
    trade: str
    item_type: str
    description: str
    quantity: float = Field(ge=0)
    unit: str
    unit_cost: float = Field(ge=0)
    waste_factor: float = Field(default=0, ge=0)
    complexity_multiplier: float = Field(default=1, ge=0)
    line_cost: float = Field(ge=0)


class LaborTaskCreate(BaseModel):
    name: str
    trade: str
    unit: str
    base_labor_cost: float = Field(ge=0)
    minimum_charge: float = Field(default=0, ge=0)
    default_multiplier: float = Field(default=1, ge=0)
    applies_to_project_type: str = "both"
    active: bool = True
    notes: str | None = None


class LaborTaskRead(LaborTaskCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ComplexityRuleCreate(BaseModel):
    trade: str
    condition_name: str
    multiplier: float = Field(ge=0)


class ComplexityRuleRead(ComplexityRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class QuoteLaborLineItemInput(BaseModel):
    trade: str
    labor_method: str
    task_name: str
    quantity: float = Field(ge=0)
    unit: str
    base_rate: float = Field(ge=0)
    complexity_multiplier: float = Field(default=1, ge=0)
    minimum_charge: float = Field(default=0, ge=0)
    calculated_cost: float = Field(default=0, ge=0)
    manual_override_cost: float | None = None
    final_cost: float = Field(default=0, ge=0)
    override_reason: str | None = None
    notes: str | None = None


class QuoteLaborLineItemRead(QuoteLaborLineItemInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_id: int
    created_at: datetime | None = None
