from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.services.gemini_client import generate_text


def _bar_chart(data: dict[str, float], title: str, path: Path, ylabel: str) -> str | None:
    if not data:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(labels, values, color="#2563eb")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)


def generate_report(state: dict) -> dict:
    analysis = state.get("analysis") or {}
    anomalies = state.get("anomalies") or []
    budget = state.get("budget") or {}
    transactions = state.get("transactions") or []

    reports_dir = Path("reports")
    category_chart = _bar_chart(
        analysis.get("by_category") or {},
        "Spend by Category",
        reports_dir / "spend_by_category.png",
        "Amount",
    )
    month_chart = _bar_chart(
        analysis.get("by_month") or {},
        "Spend by Month",
        reports_dir / "spend_by_month.png",
        "Amount",
    )

    prompt = (
        "Write a concise personal finance briefing for a dashboard. "
        f"Analysis: {analysis}. Anomalies: {anomalies[:8]}. "
        f"Budget: {budget}. Use short paragraphs and 4-6 bullet recommendations."
    )
    insights = generate_text(prompt)
    if not insights:
        top_cat = analysis.get("largest_category") or "spending"
        insights = (
            f"Total recorded spend is {analysis.get('total_spend', 0)}. "
            f"The largest category is {top_cat}. "
            f"{analysis.get('unnecessary_count', 0)} discretionary transactions total "
            f"{analysis.get('unnecessary_total', 0)}. "
            f"{len(anomalies)} transactions were flagged as unusual or duplicate. "
            f"Suggested monthly budget is {budget.get('suggested_monthly_total', 0)} "
            f"with about {budget.get('potential_monthly_savings', 0)} in savings opportunity.\n\n"
            "Recommendations:\n"
            "- Review flagged anomalies and duplicate charges first.\n"
            "- Set category caps close to the suggested budgets.\n"
            "- Reduce impulse shopping and dining-out where overspend appears.\n"
            "- Keep essential bills and housing funded before discretionary spend."
        )

    report = {
        "headline": "Expense analysis complete",
        "transaction_count": len(transactions),
        "total_spend": analysis.get("total_spend"),
        "anomaly_count": len(anomalies),
        "charts": {"by_category": category_chart, "by_month": month_chart},
        "insights": insights,
        "strategies": budget.get("strategies") or [],
    }
    return {"report": report, "insights": insights}
