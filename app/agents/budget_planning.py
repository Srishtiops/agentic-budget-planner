from __future__ import annotations

from collections import defaultdict

from app.services.gemini_client import generate_json

NEEDS = {"Groceries", "Bills", "Housing", "Healthcare", "Education", "Travel"}


def plan_budget(state: dict) -> dict:
    transactions = state.get("transactions") or []
    user_limits = state.get("user_limits") or {}
    monthly_income = float(state.get("monthly_income") or 0.0)
    savings_goal = float(state.get("savings_goal") or 0.0)

    by_month_category: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    months: set[str] = set()
    for tx in transactions:
        date = str(tx.get("date") or "")
        month = date[:7] if len(date) >= 7 else "unknown"
        months.add(month)
        by_month_category[month][tx.get("category") or "Other"] += float(tx.get("amount") or 0)

    month_count = max(len(months), 1)
    avg_by_category: dict[str, float] = defaultdict(float)
    for month_map in by_month_category.values():
        for category, amount in month_map.items():
            avg_by_category[category] += amount
    for category in list(avg_by_category):
        avg_by_category[category] = round(avg_by_category[category] / month_count, 2)

    all_categories = sorted(set(list(avg_by_category.keys()) + [c for c, v in user_limits.items() if float(v or 0) > 0]))

    total_actual_monthly_spend = round(sum(avg_by_category.values()), 2)
    actual_cash_flow = round(monthly_income - total_actual_monthly_spend, 2) if monthly_income > 0 else 0.0

    total_user_limits = round(sum(float(v) for v in user_limits.values() if v and float(v) > 0), 2)
    planned_cash_flow = round(monthly_income - total_user_limits, 2) if (monthly_income > 0 and total_user_limits > 0) else 0.0

    recommendations = []
    suggested_total = 0.0
    for category in all_categories:
        avg = avg_by_category.get(category, 0.0)
        raw_limit = user_limits.get(category)
        user_limit = float(raw_limit) if raw_limit not in (None, 0, 0.0, "") else None

        if category in NEEDS:
            suggested = round(avg * 1.05, 2) if avg > 0 else (user_limit or 0.0)
        else:
            suggested = round(avg * 0.85, 2) if avg > 0 else (user_limit or 0.0)

        # If user explicitly set a limit, consider it
        if user_limit is not None:
            # If user limit is lower than avg, cap it at user limit
            if user_limit < avg:
                suggested = user_limit

        over = user_limit is not None and avg > float(user_limit)
        savings_opp = round(max(avg - suggested, 0), 2)
        recommendations.append(
            {
                "category": category,
                "average_monthly_spend": avg,
                "suggested_budget": suggested,
                "user_limit": user_limit,
                "over_user_limit": over,
                "savings_opportunity": savings_opp,
            }
        )
        suggested_total += suggested

    suggested_total = round(suggested_total, 2)
    potential_savings = round(sum(item["savings_opportunity"] for item in recommendations), 2)

    income_note = None
    if monthly_income > 0:
        remaining = round(monthly_income - suggested_total, 2)
        is_planned_deficit = total_user_limits > monthly_income
        is_actual_deficit = total_actual_monthly_spend > monthly_income
        is_suggested_deficit = remaining < 0

        # Meets savings goal requires positive cash flow after budget AND no planned budget deficit
        meets_goal = (remaining >= savings_goal) and (not is_planned_deficit) and (planned_cash_flow >= savings_goal if total_user_limits > 0 else True)

        income_note = {
            "monthly_income": monthly_income,
            "actual_monthly_spend": total_actual_monthly_spend,
            "actual_net_cash_flow": actual_cash_flow,
            "is_actual_deficit": is_actual_deficit,
            "total_user_limits": total_user_limits,
            "planned_cash_flow": planned_cash_flow,
            "is_planned_deficit": is_planned_deficit,
            "suggested_spend": suggested_total,
            "leftover_after_budget": remaining,
            "is_suggested_deficit": is_suggested_deficit,
            "meets_savings_goal": meets_goal,
            "savings_shortfall": round(max(0, savings_goal - planned_cash_flow if is_planned_deficit else savings_goal - remaining), 2),
        }

    # Prompt LLM with deficit awareness
    prompt = (
        "You are a personal finance planner. Analyze this financial scenario:\n"
        f"- Monthly Income: ${monthly_income}\n"
        f"- Monthly Savings Goal: ${savings_goal}\n"
        f"- Actual Average Monthly Spend: ${total_actual_monthly_spend} (Net Cash Flow: ${actual_cash_flow})\n"
        f"- User-Configured Limits: {user_limits} (Total Limits: ${total_user_limits}, Planned Cash Flow: ${planned_cash_flow})\n"
        f"- Suggested Budget Total: ${suggested_total}\n"
        "IMPORTANT: If configured limits or spending exceed monthly income, there is a CRITICAL DEFICIT / negative cash flow. "
        "Highlight the deficit prominently and advise immediate expense reductions.\n"
        'Return JSON: {"strategies":["..."]}'
    )
    llm = generate_json(prompt)
    strategies = []
    if isinstance(llm, dict):
        strategies = [str(s) for s in (llm.get("strategies") or [])[:5]]

    if not strategies:
        if monthly_income > 0 and total_user_limits > monthly_income:
            strategies = [
                f"🚨 CRITICAL DEFICIT ALERT: Your configured category limits (${total_user_limits:,.2f}) exceed your monthly income (${monthly_income:,.2f}) by -${abs(planned_cash_flow):,.2f}!",
                "Extreme Allocations: Review large caps (e.g. Shopping or Travel) that cannot be sustained on your current income.",
                f"Unmet Savings Target: You will not save your target ${savings_goal:,.2f}/month; this budget produces a monthly loss / debt accumulation.",
                "Adjust all category caps to ensure total planned budget is below your monthly income.",
            ]
        elif monthly_income > 0 and total_actual_monthly_spend > monthly_income:
            strategies = [
                f"🚨 OVERSPENDING ALERT: Actual historical spending (${total_actual_monthly_spend:,.2f}) exceeds monthly income (${monthly_income:,.2f}) by -${abs(actual_cash_flow):,.2f}.",
                "Immediate Discretionary Reductions: Trim non-essential categories (Shopping, Dining out, Entertainment).",
                "Cut discretionary categories at 85% of recent averages to restore positive cash flow.",
            ]
        else:
            strategies = [
                "Cap discretionary categories (Shopping, Entertainment, Food out) at 85% of recent averages.",
                "Keep housing, bills, groceries, and healthcare near current spend with a 5% buffer.",
                "Route duplicate/anomaly recoveries and surplus budget into an automatic savings transfer.",
            ]

    budget = {
        "recommendations": recommendations,
        "suggested_monthly_total": suggested_total,
        "potential_monthly_savings": potential_savings if not (income_note and income_note.get("is_planned_deficit")) else planned_cash_flow,
        "income": income_note,
        "strategies": strategies,
    }
    return {"budget": budget}
