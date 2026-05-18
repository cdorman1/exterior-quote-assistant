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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="quotes")
    line_items: Mapped[list["QuoteLineItem"]] = relationship(back_populates="quote")
    labor_line_items: Mapped[list["QuoteLaborLineItem"]] = relationship(back_populates="quote")


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


class ChangeOrderRate(Base):
    __tablename__ = "change_order_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
