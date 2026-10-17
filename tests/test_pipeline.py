from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.anomaly_detection import detect_anomalies
from app.agents.categorization import categorize_transactions
from app.agents.graph import run_expense_pipeline
from app.main import app
from app.services.ingest import parse_transactions_csv

SAMPLE = Path("sample_data/transactions.csv")


def test_ingest_public_dataset():
    rows = parse_transactions_csv(SAMPLE.read_text(encoding="utf-8"))
    assert len(rows) >= 200
    assert {"date", "description", "merchant", "amount"} <= set(rows[0])
    assert all(row["amount"] > 0 for row in rows)


def test_categorization_known_merchants():
    state = {
        "transactions": [
            {"date": "2013-01-07", "description": "SAFEWAY STORE 2606", "merchant": "Safeway", "amount": 85.47},
            {"date": "2013-01-15", "description": "STARBUCKS #05752", "merchant": "Starbucks", "amount": 7.10},
            {"date": "2013-01-03", "description": "SH DRAFT mortgage", "merchant": "Mortgage & Rent", "amount": 2400.0},
        ]
    }
    out = categorize_transactions(state)["transactions"]
    assert out[0]["category"] == "Groceries"
    assert out[1]["category"] == "Food"
    assert out[2]["category"] == "Housing"


def test_anomaly_flags_extreme_and_duplicate():
    txs = [
        {"date": "2013-01-01", "description": "Coffee", "merchant": "Cafe", "amount": 5.0, "category": "Food"},
        {"date": "2013-01-02", "description": "Coffee", "merchant": "Cafe", "amount": 5.5, "category": "Food"},
        {"date": "2013-01-03", "description": "Coffee", "merchant": "Cafe", "amount": 4.8, "category": "Food"},
        {"date": "2013-01-04", "description": "Coffee", "merchant": "Cafe", "amount": 6.0, "category": "Food"},
        {"date": "2013-01-05", "description": "Luxury watch", "merchant": "LuxeTime", "amount": 2480.0, "category": "Shopping"},
        {"date": "2013-01-06", "description": "Coffee", "merchant": "Cafe", "amount": 5.0, "category": "Food"},
    ]
    result = detect_anomalies({"transactions": txs})
    amounts = {item["amount"] for item in result["anomalies"]}
    assert 2480.0 in amounts
    assert any("duplicate" in " ".join(item["reasons"]).lower() for item in result["anomalies"])


def test_full_pipeline_on_public_sample():
    rows = parse_transactions_csv(SAMPLE.read_text(encoding="utf-8"))[:80]
    result = run_expense_pipeline(
        {
            "transactions": rows,
            "user_limits": {"Food": 400, "Shopping": 250},
            "monthly_income": 6000,
            "savings_goal": 500,
        }
    )
    assert result["analysis"]["transaction_count"] == 80
    assert result["analysis"]["total_spend"] > 0
    assert result["budget"]["recommendations"]
    assert result["report"]["insights"]
    assert Path("reports/spend_by_category.png").exists()


def test_health_endpoint():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"


def test_api_sample_and_analyze(tmp_path, monkeypatch):
    monkeypatch.chdir(Path.cwd())
    client = TestClient(app)
    loaded = client.post("/transactions/sample", params={"name": "spendalyzer"})
    assert loaded.status_code == 200
    assert loaded.json()["loaded"] >= 200
    analyzed = client.post("/analyze", json={"monthly_income": 6000, "savings_goal": 500})
    assert analyzed.status_code == 200
    body = analyzed.json()
    assert body["analysis"]["transaction_count"] >= 200
    assert body["budget"]["recommendations"]
    latest = client.get("/reports/latest")
    assert latest.status_code == 200
    assert client.get("/anomalies").status_code == 200
