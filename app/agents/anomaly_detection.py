from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.ensemble import IsolationForest


def _duplicate_keys(transactions: list[dict]) -> set[int]:
    seen: dict[tuple, list[int]] = defaultdict(list)
    for i, tx in enumerate(transactions):
        key = (
            str(tx.get("merchant") or "").lower().strip(),
            round(float(tx.get("amount") or 0), 2),
            str(tx.get("description") or "").lower().strip()[:40],
        )
        seen[key].append(i)
    flagged = set()
    for indexes in seen.values():
        if len(indexes) > 1:
            flagged.update(indexes[1:])
    return flagged


def detect_anomalies(state: dict) -> dict:
    transactions = state.get("transactions") or []
    if not transactions:
        return {"anomalies": [], "transactions": transactions}

    amounts = np.array([[float(tx.get("amount") or 0)] for tx in transactions], dtype=float)
    contamination = min(0.15, max(0.05, 3 / max(len(transactions), 1)))
    model = IsolationForest(contamination=contamination, random_state=42)
    labels = model.fit_predict(amounts)
    scores = model.decision_function(amounts)
    duplicates = _duplicate_keys(transactions)

    # Compute category averages and percentiles for context
    p95 = float(np.percentile(amounts, 95)) if len(amounts) > 0 else 0.0
    median_val = float(np.median(amounts)) if len(amounts) > 0 else 0.0

    cat_totals: dict[str, list[float]] = defaultdict(list)
    for tx in transactions:
        cat = str(tx.get("category") or "Other")
        cat_totals[cat].append(float(tx.get("amount") or 0))
    cat_means = {cat: float(np.mean(vals)) for cat, vals in cat_totals.items()}

    anomalies = []
    for i, tx in enumerate(transactions):
        amount = float(tx.get("amount") or 0)
        score = float(-scores[i])
        is_iso = labels[i] == -1
        is_dup = i in duplicates
        is_extreme = amount >= p95 and amount > 50.0
        flagged = bool(is_iso or is_dup or is_extreme)

        reasons = []
        alert_type = "Unusual Expense"
        cat = str(tx.get("category") or "Other")
        merchant = str(tx.get("merchant") or tx.get("description") or "Merchant")
        cat_avg = cat_means.get(cat, median_val)

        if is_dup:
            alert_type = "Duplicate Charge"
            reasons.append(f"Possible duplicate transaction of ${amount:,.2f} detected at {merchant}")
        elif is_extreme:
            alert_type = "Extreme High Spend"
            reasons.append(f"High-value purchase: ${amount:,.2f} is in the top 5% of all expenses (typical median is ${median_val:,.2f})")
        elif is_iso:
            alert_type = "Spending Spike"
            if cat_avg > 0 and amount > cat_avg * 1.5:
                reasons.append(f"Unusual spike: ${amount:,.2f} is much higher than your average {cat} spend of ~${cat_avg:,.2f}")
            else:
                reasons.append(f"Unusual amount: ${amount:,.2f} deviates significantly from typical spending patterns")

        tx["is_anomaly"] = flagged
        tx["anomaly_score"] = round(score, 4)
        tx["notes"] = "; ".join(reasons)
        tx["alert_type"] = alert_type if flagged else ""

        if flagged:
            anomalies.append(
                {
                    "date": tx.get("date"),
                    "description": tx.get("description"),
                    "merchant": merchant,
                    "amount": amount,
                    "category": cat,
                    "alert_type": alert_type,
                    "anomaly_score": tx["anomaly_score"],
                    "reasons": reasons,
                    "explanation": reasons[0] if reasons else "Unusual spending pattern flagged.",
                }
            )

    anomalies.sort(key=lambda item: item["amount"], reverse=True)
    return {"transactions": transactions, "anomalies": anomalies}
