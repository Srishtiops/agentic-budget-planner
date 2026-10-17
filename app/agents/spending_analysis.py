from collections import defaultdict

UNNECESSARY_HINTS = (
    "impulse",
    "gadget",
    "luxury",
    "concert",
    "movie",
    "stream",
    "coffee",
    "dinner out",
    "valentine",
    "clothing",
    "shopping",
)


def analyze_spending(state: dict) -> dict:
    transactions = state.get("transactions") or []
    by_category: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    merchant_spend: dict[str, float] = defaultdict(float)
    unnecessary: list[dict] = []

    total = 0.0
    for tx in transactions:
        amount = float(tx.get("amount") or 0)
        category = tx.get("category") or "Other"
        date = str(tx.get("date") or "")
        month = date[:7] if len(date) >= 7 else "unknown"
        merchant = tx.get("merchant") or "Unknown"
        by_category[category] += amount
        by_month[month] += amount
        merchant_spend[merchant] += amount
        total += amount

        blob = f"{tx.get('description', '')} {category}".lower()
        if any(hint in blob for hint in UNNECESSARY_HINTS) and category not in {"Bills", "Housing", "Groceries", "Healthcare"}:
            tx["is_unnecessary"] = True
            unnecessary.append(tx)
        else:
            tx["is_unnecessary"] = bool(tx.get("is_unnecessary"))

    months = sorted(by_month)
    monthly_change = None
    if len(months) >= 2:
        prev, curr = by_month[months[-2]], by_month[months[-1]]
        monthly_change = round(((curr - prev) / prev) * 100, 2) if prev else None

    top_categories = sorted(by_category.items(), key=lambda item: item[1], reverse=True)
    analysis = {
        "total_spend": round(total, 2),
        "transaction_count": len(transactions),
        "by_category": {k: round(v, 2) for k, v in top_categories},
        "by_month": {k: round(v, 2) for k, v in sorted(by_month.items())},
        "top_merchants": dict(sorted(merchant_spend.items(), key=lambda item: item[1], reverse=True)[:8]),
        "unnecessary_count": len(unnecessary),
        "unnecessary_total": round(sum(float(tx["amount"]) for tx in unnecessary), 2),
        "month_over_month_change_pct": monthly_change,
        "largest_category": top_categories[0][0] if top_categories else None,
    }
    return {"transactions": transactions, "analysis": analysis}
