from typing import Any, TypedDict


class ExpenseState(TypedDict, total=False):
    transactions: list[dict[str, Any]]
    user_limits: dict[str, float]
    monthly_income: float | None
    savings_goal: float | None
    analysis: dict[str, Any]
    anomalies: list[dict[str, Any]]
    budget: dict[str, Any]
    report: dict[str, Any]
    insights: str
