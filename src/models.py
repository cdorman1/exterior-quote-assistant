from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="customer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_scope: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="lead")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="projects")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="project")
    blueprint_files: Mapped[list["BlueprintFile"]] = relationship(back_populates="project")
    takeoff_measurements: Mapped[list["TakeoffMeasurement"]] = relationship(back_populates="project")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    default_waste_factor: Mapped[float] = mapped_column(Float, default=0.10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    prices: Mapped[list["MaterialPrice"]] = relationship(back_populates="material")


class MaterialPrice(Base):
    __tablename__ = "material_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    supplier: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, default=date.today)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    material: Mapped[Material] = relationship(back_populates="prices")


class LaborTask(Base):
    __tablename__ = "labor_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    base_labor_cost: Mapped[float] = mapped_column(Float, nullable=False)
    minimum_charge: Mapped[float] = mapped_column(Float, default=0)
    default_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    applies_to_project_type: Mapped[str] = mapped_column(String(50), default="both")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class WasteRule(Base):
    __tablename__ = "waste_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    waste_percent: Mapped[float] = mapped_column(Float, nullable=False)


class ComplexityRule(Base):
    __tablename__ = "complexity_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    quote_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    target_margin: Mapped[float] = mapped_column(Float, default=0.40)
    tax_rate: Mapped[float] = mapped_column(Float, default=0)
    permit_cost: Mapped[float] = mapped_column(Float, default=0)
    disposal_cost: Mapped[float] = mapped_column(Float, default=0)
    equipment_cost: Mapped[float] = mapped_column(Float, default=0)
    overhead_cost: Mapped[float] = mapped_column(Float, default=0)
    material_cost: Mapped[float] = mapped_column(Float, default=0)
    labor_cost: Mapped[float] = mapped_column(Float, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0)
    customer_price: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="quotes")
    line_items: Mapped[list["QuoteLineItem"]] = relationship(back_populates="quote")
    labor_line_items: Mapped[list["QuoteLaborLineItem"]] = relationship(back_populates="quote")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="quote")


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    waste_factor: Mapped[float] = mapped_column(Float, default=0)
    complexity_multiplier: Mapped[float] = mapped_column(Float, default=1)
    line_cost: Mapped[float] = mapped_column(Float, nullable=False)

    quote: Mapped[Quote] = relationship(back_populates="line_items")


class QuoteLaborLineItem(Base):
    __tablename__ = "quote_labor_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    labor_method: Mapped[str] = mapped_column(String(50), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)
    complexity_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    minimum_charge: Mapped[float] = mapped_column(Float, default=0)
    calculated_cost: Mapped[float] = mapped_column(Float, default=0)
    manual_override_cost: Mapped[float | None] = mapped_column(Float)
    final_cost: Mapped[float] = mapped_column(Float, default=0)
    override_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quote: Mapped[Quote] = relationship(back_populates="labor_line_items")


class BlueprintFile(Base):
    __tablename__ = "blueprint_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_version: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    sheet_count: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="blueprint_files")
    sheets: Mapped[list["BlueprintSheet"]] = relationship(back_populates="blueprint_file")


class BlueprintSheet(Base):
    __tablename__ = "blueprint_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blueprint_file_id: Mapped[int] = mapped_column(ForeignKey("blueprint_files.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_number: Mapped[str | None] = mapped_column(String(50))
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    sheet_type: Mapped[str] = mapped_column(String(50), default="unknown")
    scale_text: Mapped[str | None] = mapped_column(String(255))
    calibrated_scale: Mapped[str | None] = mapped_column(String(255))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    blueprint_file: Mapped[BlueprintFile] = relationship(back_populates="sheets")


class TakeoffMeasurement(Base):
    __tablename__ = "takeoff_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    blueprint_file_id: Mapped[int | None] = mapped_column(ForeignKey("blueprint_files.id"))
    blueprint_sheet_id: Mapped[int | None] = mapped_column(ForeignKey("blueprint_sheets.id"))
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="takeoff_measurements")
    blueprint_file: Mapped[BlueprintFile | None] = relationship()
    blueprint_sheet: Mapped[BlueprintSheet | None] = relationship()


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    logo_path: Mapped[str | None] = mapped_column(Text)
    license_number: Mapped[str | None] = mapped_column(String(100))
    insurance_text: Mapped[str | None] = mapped_column(Text)
    default_quote_expiration_days: Mapped[int] = mapped_column(Integer, default=30)
    default_payment_terms: Mapped[str | None] = mapped_column(Text)
    default_warranty_text: Mapped[str | None] = mapped_column(Text)
    default_footer_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    proposal_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    intro_text: Mapped[str | None] = mapped_column(Text)
    scope_text: Mapped[str | None] = mapped_column(Text)
    material_summary_text: Mapped[str | None] = mapped_column(Text)
    labor_summary_text: Mapped[str | None] = mapped_column(Text)
    assumptions_text: Mapped[str | None] = mapped_column(Text)
    exclusions_text: Mapped[str | None] = mapped_column(Text)
    change_order_text: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    warranty_text: Mapped[str | None] = mapped_column(Text)
    total_investment_text: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quote: Mapped[Quote] = relationship(back_populates="proposals")


class ChangeOrderRate(Base):
    __tablename__ = "change_order_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
