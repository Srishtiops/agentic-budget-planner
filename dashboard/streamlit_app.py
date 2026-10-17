from __future__ import annotations

import calendar
import datetime
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.graph import run_expense_pipeline
from app.database import SessionLocal, init_db
from app.models import AnalysisRun, BudgetLimit, Transaction
from app.services.ingest import parse_transactions_csv

st.set_page_config(
    page_title="AI Expense & Daily Budget Planner",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)
init_db()

BENCHMARK_PATH = ROOT / "sample_data" / "transactions.csv"

# --- Database Helpers ---
def load_transactions_from_db() -> list[dict]:
    db = SessionLocal()
    try:
        items = db.query(Transaction).order_by(Transaction.date.desc()).all()
        return [
            {
                "id": item.id,
                "date": str(item.date or ""),
                "description": str(item.description or ""),
                "merchant": str(item.merchant or ""),
                "amount": float(item.amount or 0.0),
                "category": str(item.category or "Uncategorized"),
                "is_anomaly": bool(item.is_anomaly),
                "anomaly_score": float(item.anomaly_score or 0.0),
                "is_unnecessary": bool(item.is_unnecessary),
                "notes": str(item.notes or ""),
            }
            for item in items
        ]
    finally:
        db.close()


def load_latest_run_from_db() -> dict | None:
    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).first()
        if run is None:
            return None
        summary = json.loads(run.summary_json or "{}")
        summary["insights"] = run.report_text
        return summary
    finally:
        db.close()


def persist_transactions(rows: list[dict]) -> None:
    db = SessionLocal()
    try:
        db.query(Transaction).delete()
        for row in rows:
            clean = {
                "date": str(row.get("date") or ""),
                "description": str(row.get("description") or ""),
                "merchant": str(row.get("merchant") or ""),
                "amount": float(row.get("amount") or 0.0),
                "category": str(row.get("category") or "Uncategorized"),
                "is_anomaly": bool(row.get("is_anomaly", False)),
                "anomaly_score": float(row.get("anomaly_score", 0.0)),
                "is_unnecessary": bool(row.get("is_unnecessary", False)),
                "notes": str(row.get("notes") or ""),
            }
            db.add(Transaction(**clean))
        db.commit()
    finally:
        db.close()


def add_single_transaction_to_db(tx: dict) -> None:
    db = SessionLocal()
    try:
        clean = {
            "date": str(tx.get("date") or datetime.date.today().isoformat()),
            "description": str(tx.get("description") or ""),
            "merchant": str(tx.get("merchant") or ""),
            "amount": float(tx.get("amount") or 0.0),
            "category": str(tx.get("category") or "Uncategorized"),
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "is_unnecessary": False,
            "notes": "",
        }
        db.add(Transaction(**clean))
        db.commit()
    finally:
        db.close()


def save_run(result: dict) -> None:
    db = SessionLocal()
    try:
        db.query(Transaction).delete()
        for tx in result.get("transactions") or []:
            db.add(
                Transaction(
                    date=str(tx.get("date") or ""),
                    description=str(tx.get("description") or ""),
                    merchant=str(tx.get("merchant") or ""),
                    amount=float(tx.get("amount") or 0.0),
                    category=str(tx.get("category") or "Other"),
                    is_anomaly=bool(tx.get("is_anomaly")),
                    anomaly_score=float(tx.get("anomaly_score") or 0.0),
                    is_unnecessary=bool(tx.get("is_unnecessary")),
                    notes=str(tx.get("notes") or ""),
                )
            )
        summary = {
            "analysis": result.get("analysis") or {},
            "anomalies": result.get("anomalies") or [],
            "budget": result.get("budget") or {},
            "report": result.get("report") or {},
        }
        db.add(AnalysisRun(summary_json=json.dumps(summary), report_text=result.get("insights") or ""))
        db.commit()
    finally:
        db.close()


# State Initialization
if "rows" not in st.session_state:
    existing = load_transactions_from_db()
    if existing:
        st.session_state.rows = existing
        st.session_state.source = "Database"
    elif BENCHMARK_PATH.exists():
        initial = parse_transactions_csv(BENCHMARK_PATH.read_bytes())
        persist_transactions(initial)
        st.session_state.rows = initial
        st.session_state.source = "Benchmark"
    else:
        st.session_state.rows = []
        st.session_state.source = "None"

if "result" not in st.session_state:
    st.session_state.result = load_latest_run_from_db()

# Custom Modern App Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1a1e29;
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .metric-val {
        font-size: 26px;
        font-weight: 700;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 13px;
        color: #94a3b8;
    }
    .deficit-alert {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 14px 18px;
        color: #fca5a5;
        margin-bottom: 16px;
    }
    .surplus-alert {
        background: rgba(34, 197, 94, 0.15);
        border: 1px solid #22c55e;
        border-radius: 8px;
        padding: 14px 18px;
        color: #86efac;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# App Navigation Bar
nav_col1, nav_col2 = st.columns([4, 1])
with nav_col1:
    st.markdown("## 💳 **AI Expense & Daily Budget Planner**")
with nav_col2:
    st.markdown("<p style='text-align: right; color: #10b981; font-weight: 600; padding-top: 10px;'>● System Ready</p>", unsafe_allow_html=True)

# --- Top Financial Goals & Interactive Limits Configuration ---
with st.container():
    col_inc, col_sav = st.columns(2)
    with col_inc:
        monthly_income = st.number_input("Monthly Income ($)", min_value=0.0, value=6000.0, step=100.0, key="cfg_income")
    with col_sav:
        savings_goal = st.number_input("Monthly Savings Target ($)", min_value=0.0, value=500.0, step=50.0, key="cfg_savings")

    with st.expander("⚙️ Category Budget Allocations (Click to adjust)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            lim_food = st.number_input("Food / Dining", min_value=0.0, value=400.0, step=25.0, key="lim_food")
            lim_groceries = st.number_input("Groceries", min_value=0.0, value=500.0, step=25.0, key="lim_groc")
        with c2:
            lim_shopping = st.number_input("Shopping", min_value=0.0, value=300.0, step=25.0, key="lim_shop")
            lim_entertain = st.number_input("Entertainment", min_value=0.0, value=150.0, step=25.0, key="lim_ent")
        with c3:
            lim_travel = st.number_input("Travel / Transport", min_value=0.0, value=400.0, step=25.0, key="lim_trav")
            lim_bills = st.number_input("Bills / Utilities", min_value=0.0, value=350.0, step=25.0, key="lim_bill")
        with c4:
            lim_housing = st.number_input("Housing / Rent", min_value=0.0, value=1500.0, step=50.0, key="lim_house")
            lim_health = st.number_input("Healthcare", min_value=0.0, value=200.0, step=25.0, key="lim_health")

category_limits = {
    "Food": lim_food,
    "Groceries": lim_groceries,
    "Shopping": lim_shopping,
    "Entertainment": lim_entertain,
    "Travel": lim_travel,
    "Bills": lim_bills,
    "Housing": lim_housing,
    "Healthcare": lim_health,
}

# --- REAL-TIME DYNAMIC BUDGET CALCULATIONS ---
now = datetime.date.today()
_, days_in_month = calendar.monthrange(now.year, now.month)
day_of_month = now.day

total_planned_budget = sum(category_limits.values())
planned_net_flow = monthly_income - total_planned_budget
is_planned_deficit = planned_net_flow < 0

# Daily Budget Allowance calculation
daily_allowance = (monthly_income - savings_goal) / max(days_in_month, 1)
daily_planned_flow = planned_net_flow / max(days_in_month, 1)

# Historical / Database Actuals
rows = st.session_state.rows
total_actual_spend = sum(float(r.get("amount") or 0.0) for r in rows) if rows else 0.0

# Calculate Today's Expenses
today_str = now.isoformat()
today_spend = sum(float(r.get("amount") or 0.0) for r in rows if str(r.get("date")) == today_str)
daily_remaining = daily_allowance - today_spend

# --- TOP LIVE KPI CARDS ---
kp1, kp2, kp3, kp4 = st.columns(4)
with kp1:
    st.metric(
        label="Monthly Income",
        value=f"${monthly_income:,.2f}",
        delta=f"Target: ${savings_goal:,.2f} savings",
        delta_color="off",
    )

with kp2:
    if is_planned_deficit:
        st.metric(
            label="Total Planned Limits",
            value=f"${total_planned_budget:,.2f}",
            delta=f"-${abs(planned_net_flow):,.2f} DEFICIT",
            delta_color="inverse",
        )
    else:
        st.metric(
            label="Total Planned Limits",
            value=f"${total_planned_budget:,.2f}",
            delta=f"+${planned_net_flow:,.2f} Surplus",
            delta_color="normal",
        )

with kp3:
    if is_planned_deficit:
        st.metric(
            label="Daily Budget Allowance",
            value=f"-${abs(daily_planned_flow):,.2f} / day",
            delta="Over Income!",
            delta_color="inverse",
        )
    else:
        st.metric(
            label="Daily Budget Allowance",
            value=f"${daily_allowance:,.2f} / day",
            delta=f"${daily_remaining:,.2f} left today",
            delta_color="normal" if daily_remaining >= 0 else "inverse",
        )

with kp4:
    meets_goal = (not is_planned_deficit) and (planned_net_flow >= savings_goal)
    shortfall = savings_goal - planned_net_flow if not meets_goal else 0.0
    if meets_goal:
        st.metric(
            label="Savings Target Feasibility",
            value="✅ On Track",
            delta=f"+${planned_net_flow - savings_goal:,.2f} extra buffer",
            delta_color="normal",
        )
    else:
        st.metric(
            label="Savings Target Feasibility",
            value="❌ Target Failed",
            delta=f"-${shortfall:,.2f} Shortfall",
            delta_color="inverse",
        )

# Prominent Deficit / Surplus Live Banner
if is_planned_deficit:
    st.markdown(
        f"""
        <div class="deficit-alert">
            <strong>🚨 CRITICAL MONTHLY BUDGET DEFICIT:</strong><br>
            Your allocated budget limits (<strong>${total_planned_budget:,.2f}</strong>) exceed your monthly income (<strong>${monthly_income:,.2f}</strong>)
            by <strong style="color: #ff4d4f;">-${abs(planned_net_flow):,.2f}</strong> (Burn rate: <strong style="color: #ff4d4f;">-${abs(daily_planned_flow):,.2f}/day</strong>).
            You cannot achieve your ${savings_goal:,.2f} savings target under this configuration.
        </div>
        """,
        unsafe_allow_html=True,
    )
elif not meets_goal and monthly_income > 0:
    st.markdown(
        f"""
        <div class="deficit-alert">
            <strong>⚠️ SAVINGS TARGET SHORTFALL:</strong> Your planned surplus of ${planned_net_flow:,.2f} is insufficient to meet your ${savings_goal:,.2f} monthly savings goal (Shortfall: -${shortfall:,.2f}).
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- ACTION: RUN AGENT PIPELINE ---
btn_col1, btn_col2 = st.columns([3, 1])
with btn_col1:
    run_clicked = st.button("🚀 Run Agentic AI Pipeline (5 Autonomous Agents)", type="primary", use_container_width=True)
with btn_col2:
    if st.button("🔄 Reset to Defaults", use_container_width=True):
        st.rerun()

if run_clicked:
    if not st.session_state.rows:
        st.warning("Please load or add expenses before running agent analysis.")
    else:
        with st.spinner("Agents Analyzing: Categorization → Spending Patterns → ML Anomalies → Budgeting → Report..."):
            pipeline_result = run_expense_pipeline(
                {
                    "transactions": [dict(r) for r in st.session_state.rows],
                    "user_limits": {k: v for k, v in category_limits.items() if v > 0},
                    "monthly_income": monthly_income or None,
                    "savings_goal": savings_goal or None,
                }
            )
            st.session_state.result = pipeline_result
            save_run(pipeline_result)
            st.session_state.rows = load_transactions_from_db()
            st.toast("AI Analysis Complete!", icon="✅")

st.divider()

# --- APP TABS ---
app_tab_daily, app_tab_agents, app_tab_txs = st.tabs(
    [
        "📅 Daily Budget & Expense Tracker",
        "🤖 AI Financial Intelligence (5 Agents)",
        "📋 All Transactions & Data Manager",
    ]
)

# ==========================================
# TAB 1: DAILY BUDGET & EXPENSE TRACKER
# ==========================================
with app_tab_daily:
    d_left, d_right = st.columns([1, 1])
    
    with d_left:
        st.subheader("Daily Budget Allowance")
        st.write(f"Month of **{now.strftime('%B %Y')}** (Day {day_of_month} of {days_in_month})")

        d_m1, d_m2, d_m3 = st.columns(3)
        d_m1.metric("Daily Base Target", f"${daily_allowance:,.2f}")
        d_m2.metric("Spent Today", f"${today_spend:,.2f}")
        d_m3.metric(
            "Remaining Today",
            f"${daily_remaining:,.2f}",
            delta=f"{'-$' if daily_remaining < 0 else '+$'}{abs(daily_remaining):,.2f}",
            delta_color="normal" if daily_remaining >= 0 else "inverse",
        )

        progress_val = min(1.0, max(0.0, today_spend / daily_allowance)) if daily_allowance > 0 else 1.0
        st.progress(progress_val)
        if daily_remaining < 0:
            st.error(f"⚠️ You have exceeded today's daily budget by ${abs(daily_remaining):,.2f}!")
        else:
            st.caption(f"You have ${(daily_remaining):.2f} left to spend today.")

    with d_right:
        st.subheader("➕ Quick Add Today's Expense")
        with st.form("daily_quick_add", clear_on_submit=True):
            qa_c1, qa_c2 = st.columns(2)
            with qa_c1:
                e_date = st.date_input("Date", value=now).isoformat()
                e_merchant = st.text_input("Merchant", placeholder="e.g. Starbucks, Uber, Shell")
            with qa_c2:
                e_amount = st.number_input("Amount ($)", min_value=0.01, value=15.0, step=1.0)
                e_category = st.selectbox("Category", list(category_limits.keys()) + ["Other"])
            e_desc = st.text_input("Description", placeholder="e.g. Morning coffee & sandwich")
            
            if st.form_submit_button("Add Expense to Daily Tracker", type="primary", use_container_width=True):
                new_entry = {
                    "date": e_date,
                    "merchant": e_merchant.strip() or "General",
                    "description": e_desc.strip() or e_merchant.strip() or "Expense",
                    "amount": float(e_amount),
                    "category": e_category,
                }
                add_single_transaction_to_db(new_entry)
                st.session_state.rows.insert(0, new_entry)
                st.session_state.result = None
                st.success(f"Recorded ${e_amount:.2f} at {new_entry['merchant']}!")
                st.rerun()

    st.subheader(f"Expenses Logged on {now.strftime('%Y-%m-%d')}")
    today_txs = [r for r in st.session_state.rows if str(r.get("date")) == today_str]
    if today_txs:
        st.dataframe(pd.DataFrame(today_txs)[["date", "merchant", "description", "category", "amount"]], use_container_width=True, hide_index=True)
    else:
        st.info("No expenses logged for today yet. Use the quick add form above to log daily expenses.")


# ==========================================
# TAB 2: AI FINANCIAL INTELLIGENCE (5 AGENTS)
# ==========================================
with app_tab_agents:
    result = st.session_state.result
    if result is None:
        st.info("Click **'🚀 Run Agentic AI Pipeline'** above to run the 5 autonomous agents.")
    else:
        analysis = result.get("analysis") or {}
        anomalies = result.get("anomalies") or []
        budget = result.get("budget") or {}
        report = result.get("report") or {}
        tx_df = pd.DataFrame(result.get("transactions") or st.session_state.rows)

        sub_cat, sub_spend, sub_anom, sub_budget, sub_rep = st.tabs(
            [
                "1. Categorization",
                "2. Spending & Discretionary",
                "3. Unusual Spending & Alerts",
                "4. Budget Planning",
                "5. AI Executive Report",
            ]
        )

        with sub_cat:
            cat_spend = pd.Series(analysis.get("by_category") or {}, dtype=float)
            col_cg1, col_cg2 = st.columns([1, 1])
            with col_cg1:
                st.subheader("Category Spend Distribution")
                if not cat_spend.empty:
                    st.bar_chart(cat_spend)
            with col_cg2:
                st.subheader("Breakdown by Category")
                if not cat_spend.empty:
                    ctable = pd.DataFrame({"Category": cat_spend.index, "Spend ($)": cat_spend.values})
                    ctable["Percentage"] = ((ctable["Spend ($)"] / ctable["Spend ($)"].sum()) * 100).round(1).astype(str) + "%"
                    st.dataframe(ctable, use_container_width=True, hide_index=True)

        with sub_spend:
            col_sp1, col_sp2, col_sp3 = st.columns(3)
            col_sp1.metric("Total Analyzed Spend", f"${analysis.get('total_spend', 0):,.2f}")
            col_sp2.metric("Discretionary / Unnecessary Items", analysis.get("unnecessary_count", 0))
            col_sp3.metric("Discretionary Waste Total", f"${analysis.get('unnecessary_total', 0):,.2f}")

            unnecessary = tx_df[tx_df.get("is_unnecessary") == True] if "is_unnecessary" in tx_df else pd.DataFrame()
            if not unnecessary.empty:
                st.subheader("⚠️ Unnecessary Spending Identified")
                st.dataframe(unnecessary[["date", "merchant", "description", "amount", "category"]], use_container_width=True, hide_index=True)

        with sub_anom:
            st.subheader("⚠️ Unusual Spending & Duplicate Charge Alerts")
            st.caption("Transactions flagged due to duplicate billing, extreme purchase amounts, or sudden category spending spikes.")

            dup_count = sum(1 for a in anomalies if "duplicate" in str(a.get("alert_type", "")).lower() or "duplicate" in str(a.get("reasons", "")).lower())
            tot_alert_spend = sum(float(a.get("amount") or 0.0) for a in anomalies)

            a_m1, a_m2, a_m3 = st.columns(3)
            a_m1.metric("Flagged Expenses", len(anomalies))
            a_m2.metric(
                "Duplicate Charges Detected",
                dup_count,
                delta="Verify with bank" if dup_count > 0 else "None",
                delta_color="inverse" if dup_count > 0 else "off",
            )
            a_m3.metric("Total Flagged Amount", f"${tot_alert_spend:,.2f}")

            if anomalies:
                anom_df = pd.DataFrame(anomalies)

                if "alert_type" not in anom_df.columns:
                    anom_df["alert_type"] = anom_df["reasons"].apply(
                        lambda r: "Duplicate Charge" if any("duplicate" in str(x).lower() for x in r) else "Unusual Amount"
                    )

                def get_explanation(row):
                    if row.get("explanation"):
                        return str(row["explanation"])
                    reasons = row.get("reasons")
                    if isinstance(reasons, list) and reasons:
                        return ", ".join(reasons)
                    return "Unusual transaction amount detected."

                def get_action(row):
                    atype = str(row.get("alert_type") or "").lower()
                    if "duplicate" in atype:
                        return "🔍 Check bank statement for double-billing"
                    elif "extreme" in atype:
                        return "👁️ Verify intentional high-value purchase"
                    return "💡 Review against typical budget"

                anom_df["Why It Was Flagged"] = anom_df.apply(get_explanation, axis=1)
                anom_df["Recommended Action"] = anom_df.apply(get_action, axis=1)

                display_df = anom_df.rename(
                    columns={
                        "date": "Date",
                        "merchant": "Merchant",
                        "category": "Category",
                        "amount": "Amount ($)",
                        "alert_type": "Alert Type",
                    }
                )
                cols_to_show = [
                    c for c in ["Date", "Merchant", "Category", "Amount ($)", "Alert Type", "Why It Was Flagged", "Recommended Action"]
                    if c in display_df.columns
                ]
                st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No unusual or duplicate transactions detected.")

        with sub_budget:
            st.subheader("Budget Planning & Deficit Analysis")
            if is_planned_deficit:
                st.error(f"🚨 Planned Deficit: Total limits (${total_planned_budget:,.2f}) exceed income (${monthly_income:,.2f}) by -${abs(planned_net_flow):,.2f}!")

            recs = pd.DataFrame(budget.get("recommendations") or [])
            if not recs.empty:
                if "user_limit" in recs.columns:
                    recs["Status"] = recs["user_limit"].apply(
                        lambda l: "🚨 Exceeds Total Income!" if l and monthly_income > 0 and l > monthly_income else ("Set" if l else "None")
                    )
                st.dataframe(recs, use_container_width=True, hide_index=True)

            st.subheader("💡 Actionable Recommendations")
            for strat in budget.get("strategies") or []:
                st.markdown(f"- {strat}")

        with sub_rep:
            st.subheader("AI Executive Insights (Google Gemini)")
            insights_content = report.get("insights") or result.get("insights") or ""
            st.markdown(insights_content)

            st.subheader("Generated Visualizations")
            charts = report.get("charts") or {}
            c_r1, c_r2 = st.columns(2)
            c_chart = charts.get("by_category") or ROOT / "reports" / "spend_by_category.png"
            m_chart = charts.get("by_month") or ROOT / "reports" / "spend_by_month.png"
            with c_r1:
                if Path(c_chart).exists():
                    st.image(str(c_chart), caption="Spend by Category")
            with c_r2:
                if Path(m_chart).exists():
                    st.image(str(m_chart), caption="Spend by Month")

            doc_report_path = ROOT / "Agentic_AI_Project_Report.docx"
            if doc_report_path.exists():
                st.divider()
                st.download_button(
                    label="📄 Download Word Assessment Report (.docx)",
                    data=doc_report_path.read_bytes(),
                    file_name="Agentic_AI_Project_Report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )


# ==========================================
# TAB 3: ALL TRANSACTIONS & DATA MANAGER
# ==========================================
with app_tab_txs:
    st.subheader("Transactions Database")
    
    dt_c1, dt_c2, dt_c3 = st.columns([2, 1, 1])
    with dt_c1:
        st.write(f"Active count: **{len(st.session_state.rows)} transactions** | Total spend: **${total_actual_spend:,.2f}**")
    with dt_c2:
        if st.button("🧪 Load Benchmark Dataset (289 items)", use_container_width=True):
            if BENCHMARK_PATH.exists():
                b_rows = parse_transactions_csv(BENCHMARK_PATH.read_bytes())
                persist_transactions(b_rows)
                st.session_state.rows = b_rows
                st.session_state.result = None
                st.success("Benchmark loaded!")
                st.rerun()
    with dt_c3:
        if st.button("🗑️ Clear Transactions", use_container_width=True):
            persist_transactions([])
            st.session_state.rows = []
            st.session_state.result = None
            st.rerun()

    uploaded = st.file_uploader("Import Bank CSV", type=["csv"])
    if uploaded is not None:
        dig = hashlib.sha256(uploaded.getvalue()).hexdigest()
        if st.session_state.get("up_dig") != dig:
            st.session_state.up_dig = dig
            p_rows = parse_transactions_csv(uploaded.getvalue())
            persist_transactions(p_rows)
            st.session_state.rows = p_rows
            st.session_state.result = None
            st.success(f"Imported {len(p_rows)} transactions!")
            st.rerun()

    if st.session_state.rows:
        tdf = pd.DataFrame(st.session_state.rows)
        disp_cols = [c for c in ["date", "merchant", "description", "amount", "category"] if c in tdf.columns]
        st.dataframe(tdf[disp_cols], use_container_width=True, hide_index=True)
