"""Run the agent pipeline from the command line and write reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.agents.graph import run_expense_pipeline
from app.services.ingest import parse_transactions_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze expenses with the Flexi agent workflow")
    parser.add_argument("--csv", default="sample_data/transactions.csv", help="Path to a transactions CSV")
    parser.add_argument("--income", type=float, default=6000.0)
    parser.add_argument("--savings", type=float, default=500.0)
    parser.add_argument("--out", default="reports/latest_analysis.json")
    args = parser.parse_args()

    path = Path(args.csv)
    rows = parse_transactions_csv(path.read_bytes())
    result = run_expense_pipeline(
        {
            "transactions": rows,
            "user_limits": {"Food": 400, "Shopping": 300, "Entertainment": 150},
            "monthly_income": args.income,
            "savings_goal": args.savings,
        }
    )
    output = {
        "source": str(path),
        "count": len(rows),
        "analysis": result.get("analysis"),
        "anomalies": result.get("anomalies"),
        "budget": result.get("budget"),
        "report": result.get("report"),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Analyzed {len(rows)} transactions from {path}")
    print(f"Total spend: {result['analysis']['total_spend']}")
    print(f"Anomalies: {len(result.get('anomalies') or [])}")
    print(f"Suggested monthly budget: {result['budget']['suggested_monthly_total']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
