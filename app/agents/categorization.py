from collections.abc import Iterable

from app.services.gemini_client import CATEGORIES, generate_json
from app.services.taxonomy import map_category

KEYWORD_MAP: list[tuple[str, Iterable[str]]] = [
    ("Groceries", ["grocery", "grocer", "freshmart", "supermarket", "safeway", "whole foods", "costco", "trader joe", "patel", "shaws", "superette"]),
    ("Food", ["cafe", "coffee", "starbucks", "dunkin", "lunch", "dinner", "bistro", "restaurant", "pastry", "chipotle", "mcdonald", "wendy", "fast food", "pizza", "sushi", "thai", "seafood", "burrito", "dining"]),
    ("Travel", ["flight", "hotel", "uber", "lyft", "airbnb", "metro", "transit", "fuel", "gas & fuel", "gasoline", "chevron", "exxon", "airport", "air travel", "skyair", "stayinn", "parking", "fastrak", "clipper", "mta", "vacation"]),
    ("Shopping", ["amazon", "paypal", "ebay", "urbanwear", "clothing", "shopping", "gadget", "bookstore", "pageturn", "target", "walmart", "macy", "nike", "adidas", "gap", "rei", "ikea"]),
    ("Bills", ["electric", "utility", "utilities", "powerco", "eversource", "internet", "comcast", "netwave", "mobile", "talknet", "phone", "water", "aqua", "pg&e", "pacific gas", "insurance"]),
    ("Entertainment", ["streamflix", "netflix", "spotify", "youtube", "movie", "cinema", "cine", "concert", "livearena", "gym", "fitness", "fithub", "amusement", "music"]),
    ("Healthcare", ["pharmacy", "healthplus", "clinic", "hospital", "cvs", "doctor", "dental", "health"]),
    ("Education", ["course", "learnlab", "tuition", "school", "udemy", "education"]),
    ("Housing", ["rent", "cityhomes", "mortgage", "housing"]),
]


def _rule_category(description: str, merchant: str) -> str:
    blob = f"{description} {merchant}".lower()
    for category, keywords in KEYWORD_MAP:
        if any(keyword in blob for keyword in keywords):
            return category
    return "Other"


def categorize_transactions(state: dict) -> dict:
    transactions = list(state.get("transactions") or [])
    pending = [
        {
            "index": i,
            "description": tx.get("description", ""),
            "merchant": tx.get("merchant", ""),
            "amount": tx.get("amount", 0),
        }
        for i, tx in enumerate(transactions)
        if not map_category(tx.get("category")) and (
            not tx.get("category") or tx.get("category") in {"", "Uncategorized"}
        )
    ]

    llm_map: dict[int, str] = {}
    if pending and len(pending) <= 60:
        payload = generate_json(
            "Classify each personal expense into exactly one category from "
            f"{CATEGORIES}. Input: {pending}. "
            'Output JSON: {"items":[{"index":0,"category":"Food"}]}'
        )
        if isinstance(payload, dict):
            for item in payload.get("items") or []:
                try:
                    idx = int(item["index"])
                    category = str(item.get("category") or "Other")
                    llm_map[idx] = category if category in CATEGORIES else "Other"
                except (KeyError, TypeError, ValueError):
                    continue

    for i, tx in enumerate(transactions):
        mapped = map_category(tx.get("category"))
        if mapped:
            tx["category"] = mapped
        elif i in llm_map:
            tx["category"] = llm_map[i]
        else:
            tx["category"] = _rule_category(tx.get("description", ""), tx.get("merchant", ""))
    return {"transactions": transactions}
