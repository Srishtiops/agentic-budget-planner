from __future__ import annotations

from datetime import datetime
from io import StringIO
import math
from typing import Any

import pandas as pd

from app.services.taxonomy import map_category

DATE_COLS = ("date", "Date", "transaction_date", "txn_date")
DESC_COLS = ("description", "Description", "Original Description", "title", "Title", "note", "Note", "Transaction Description")
MERCHANT_COLS = ("merchant", "Merchant", "Description", "account", "Account")
AMOUNT_COLS = ("amount", "Amount")
TYPE_COLS = ("type", "Type", "Transaction Type", "Income/Expense")
SKIP_TYPES = {"credit", "income", "transfer"}
SKIP_CATEGORIES = {
    "credit card payment",
    "income",
    "gift received",
    "dividend & cap gains",
    "investments",
    "transfer",
    "salary",
}


def _first(row: dict[str, Any], names: tuple[str, ...], default: str = "") -> str:
    for name in names:
        if name in row and pd.notna(row[name]) and str(row[name]).strip():
            return str(row[name]).strip()
    return default


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return value[:10]
    return parsed.date().isoformat()


def parse_transactions_csv(content: str | bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    if not text.strip():
        raise ValueError("CSV file is empty")
    try:
        frame = pd.read_csv(StringIO(text))
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV file has no header or rows") from exc
    if frame.empty:
        raise ValueError("CSV file has no transaction rows")
    if not any(column in frame.columns for column in DATE_COLS):
        raise ValueError("CSV must include a date column")
    if not any(column in frame.columns for column in DESC_COLS + MERCHANT_COLS):
        raise ValueError("CSV must include a description or merchant column")
    if not any(column in frame.columns for column in AMOUNT_COLS):
        raise ValueError("CSV must include an amount column")

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        txn_type = _first(row, TYPE_COLS).lower()
        category = _first(row, ("category", "Category")).lower()
        if txn_type in SKIP_TYPES or category in SKIP_CATEGORIES:
            continue
        amount_raw = _first(row, AMOUNT_COLS, "0")
        try:
            amount = abs(float(str(amount_raw).replace(",", "").replace("$", "")))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(amount) or amount <= 0:
            continue
        merchant = _first(row, MERCHANT_COLS)
        description = _first(row, DESC_COLS, merchant)
        mapped = map_category(_first(row, ("category", "Category", "Category_Raw")))
        date = _parse_date(_first(row, DATE_COLS))
        if not date:
            continue
        records.append(
            {
                "date": date,
                "description": description,
                "merchant": merchant or description.split(",")[0][:80],
                "amount": round(amount, 2),
                "category": mapped or "Uncategorized",
            }
        )
    return records
