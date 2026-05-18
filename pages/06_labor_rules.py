from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_auth
from src.constants import PROJECT_TYPES, TRADES
from src.database import SessionLocal, init_db
from src.models import ComplexityRule, LaborTask, WasteRule

require_auth()
st.title("Labor Rules")
init_db()
db = SessionLocal()
try:
    st.subheader("Add labor task")
    with st.form("add_labor_task"):
        task_name = st.text_input("Name")
        trade = st.selectbox("Trade", TRADES)
        unit = st.text_input("Unit", value="square")
        base_labor_cost = st.number_input("Base labor cost", min_value=0.0, value=0.0, step=1.0)
        minimum_charge = st.number_input("Minimum charge", min_value=0.0, value=0.0, step=1.0)
        default_multiplier = st.number_input("Default multiplier", min_value=0.0, value=1.0, step=0.01)
        applies_to_project_type = st.selectbox("Applies to project type", ["both", *PROJECT_TYPES])
        active = st.checkbox("Active", value=True)
        notes = st.text_area("Notes")
        if st.form_submit_button("Save labor task") and task_name:
            db.add(
                LaborTask(
                    name=task_name,
                    trade=trade,
                    unit=unit,
                    base_labor_cost=base_labor_cost,
                    minimum_charge=minimum_charge,
                    default_multiplier=default_multiplier,
                    applies_to_project_type=applies_to_project_type,
                    active=active,
                    notes=notes,
                )
            )
            db.commit()
            st.success("Labor task saved.")
            st.rerun()

    st.subheader("Labor tasks")
    labor_tasks = db.query(LaborTask).order_by(LaborTask.trade, LaborTask.name).all()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": t.id,
                    "Name": t.name,
                    "Trade": t.trade,
                    "Unit": t.unit,
                    "Base Labor Cost": t.base_labor_cost,
                    "Minimum Charge": t.minimum_charge,
                    "Default Multiplier": t.default_multiplier,
                    "Applies To Project Type": t.applies_to_project_type,
                    "Active": t.active,
                    "Notes": t.notes,
                }
                for t in labor_tasks
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Add complexity rule")
    with st.form("add_complexity_rule"):
        rule_trade = st.selectbox("Trade", TRADES, key="complexity_trade")
        condition_name = st.text_input("Condition name")
        multiplier = st.number_input("Multiplier", min_value=0.0, value=1.0, step=0.01)
        if st.form_submit_button("Save complexity rule") and condition_name:
            db.add(ComplexityRule(trade=rule_trade, condition_name=condition_name, multiplier=multiplier))
            db.commit()
            st.success("Complexity rule saved.")
            st.rerun()

    st.subheader("Complexity rules")
    complexity_rules = db.query(ComplexityRule).order_by(ComplexityRule.trade, ComplexityRule.condition_name).all()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": r.id,
                    "Trade": r.trade,
                    "Condition": r.condition_name,
                    "Multiplier": r.multiplier,
                }
                for r in complexity_rules
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Waste rules")
    st.dataframe(
        pd.DataFrame([r.__dict__ for r in db.query(WasteRule).filter(WasteRule.trade.in_(TRADES)).all()]).drop(
            columns=["_sa_instance_state"],
            errors="ignore",
        ),
        use_container_width=True,
        hide_index=True,
    )
finally:
    db.close()
