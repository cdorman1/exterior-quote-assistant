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


class BlueprintFileCreate(BaseModel):
    project_id: int
    original_file_name: str
    stored_file_name: str
    file_path: str
    file_type: str
    file_size_bytes: int
    plan_version: str | None = None
    description: str | None = None
    extracted_text: str | None = None
    sheet_count: int | None = None
    notes: str | None = None
    is_active: bool = True


class BlueprintFileRead(BlueprintFileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: datetime


class BlueprintSheetCreate(BaseModel):
    blueprint_file_id: int
    page_number: int
    sheet_number: str | None = None
    sheet_name: str | None = None
    sheet_type: str = "unknown"
    scale_text: str | None = None
    calibrated_scale: str | None = None
    extracted_text: str | None = None
    confidence_score: float = 0


class BlueprintSheetRead(BlueprintSheetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class TakeoffMeasurementCreate(BaseModel):
    project_id: int
    blueprint_file_id: int | None = None
    blueprint_sheet_id: int | None = None
    trade: str
    measurement_type: str
    quantity: float = Field(ge=0)
    unit: str
    source: str
    confidence_score: float = 0
    approved: bool = False
    approved_by: str | None = None
    notes: str | None = None


class TakeoffMeasurementRead(TakeoffMeasurementCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CompanySettingsCreate(BaseModel):
    company_name: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    logo_path: str | None = None
    license_number: str | None = None
    insurance_text: str | None = None
    default_quote_expiration_days: int = 30
    default_payment_terms: str | None = None
    default_warranty_text: str | None = None
    default_footer_text: str | None = None


class CompanySettingsRead(CompanySettingsCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProposalCreate(BaseModel):
    quote_id: int
    proposal_number: str
    status: str = "draft"
    title: str
    intro_text: str | None = None
    scope_text: str | None = None
    material_summary_text: str | None = None
    labor_summary_text: str | None = None
    assumptions_text: str | None = None
    exclusions_text: str | None = None
    change_order_text: str | None = None
    payment_terms: str | None = None
    warranty_text: str | None = None
    total_investment_text: str | None = None
    pdf_path: str | None = None


class ProposalRead(ProposalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
