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
