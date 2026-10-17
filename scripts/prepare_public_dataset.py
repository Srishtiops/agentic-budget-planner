"""Normalize public expense CSVs into date,description,merchant,amount."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.taxonomy import map_category

SAMPLE = ROOT / "sample_data"

SKIP_CATEGORIES = {
    "credit card payment",
    "income",
    "gift received",
    "dividend & cap gains",
    "investments",
    "transfer",
}


def parse_date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value[:10]


def from_spendalyzer(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (row.get("Transaction Type") or "").lower() != "debit":
                continue
            category = (row.get("Category") or "").strip()
            if category.lower() in SKIP_CATEGORIES:
                continue
            merchant = (row.get("Description") or "").strip()
            description = (row.get("Original Description") or merchant).strip()
            amount = abs(float(row.get("Amount") or 0))
            if amount <= 0:
                continue
            rows.append(
                {
                    "date": parse_date(row.get("Date") or ""),
                    "description": description,
                    "merchant": merchant,
                    "amount": f"{amount:.2f}",
                    "category": map_category(category) or "Uncategorized",
                }
            )
    return rows


def from_github_expenses(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            amount = abs(float(row.get("Amount") or 0))
            if amount <= 0:
                continue
            description = (row.get("Description") or "").strip()
            rows.append(
                {
                    "date": parse_date(row.get("Date") or ""),
                    "description": description,
                    "merchant": description,
                    "amount": f"{amount:.2f}",
                    "category": map_category(row.get("Category")) or "Uncategorized",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["date", "description", "merchant", "amount", "category"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    spendalyzer = from_spendalyzer(SAMPLE / "spendalyzer_transactions_3mos.csv")
    github_exp = from_github_expenses(SAMPLE / "github_personal_expenses.csv")
    write_csv(SAMPLE / "transactions.csv", spendalyzer)
    write_csv(SAMPLE / "transactions_recent_personal.csv", github_exp)
    write_csv(SAMPLE / "sample_transactions.csv", spendalyzer)
    print(f"Spendalyzer expenses: {len(spendalyzer)} -> sample_data/transactions.csv")
    print(f"GitHub personal expenses: {len(github_exp)} -> sample_data/transactions_recent_personal.csv")


if __name__ == "__main__":
    main()
