from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.graph import run_expense_pipeline
from app.database import get_db, init_db
from app.models import AnalysisRun, BudgetLimit, Transaction
from app.schemas import AnalyzeRequest, BudgetLimitIn
from app.services.ingest import parse_transactions_csv

SAMPLE_FILES = {
    "benchmark": Path("sample_data/transactions.csv"),
    "spendalyzer": Path("sample_data/transactions.csv"),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path("data").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Flexi Expense Planner",
    description="Agentic AI-based intelligent expense analysis and budget planner",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/transactions")
def add_transaction(payload: TransactionIn, db: Session = Depends(get_db)):
    tx = Transaction(
        date=payload.date,
        description=payload.description,
        merchant=payload.merchant or "",
        amount=payload.amount,
        category="Uncategorized",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return {
        "id": tx.id,
        "date": tx.date,
        "description": tx.description,
        "merchant": tx.merchant,
        "amount": tx.amount,
        "category": tx.category,
    }


@app.post("/transactions/sample")
def load_sample(name: str = "benchmark", db: Session = Depends(get_db)):
    path = SAMPLE_FILES.get(name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Unknown sample. Use benchmark.")
    rows = parse_transactions_csv(path.read_bytes())
    db.query(Transaction).delete()
    for row in rows:
        db.add(Transaction(**row))
    db.commit()
    return {"loaded": len(rows), "sample": name, "source": str(path)}


@app.post("/transactions/upload")
def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = file.file.read()
    try:
        rows = parse_transactions_csv(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="No expense rows found in the CSV")
    db.query(Transaction).delete()
    for row in rows:
        db.add(Transaction(**row))
    db.commit()
    return {"loaded": len(rows)}


@app.get("/transactions")
def list_transactions(db: Session = Depends(get_db)):
    items = db.query(Transaction).order_by(Transaction.date.desc()).all()
    return [
        {
            "id": item.id,
            "date": item.date,
            "description": item.description,
            "merchant": item.merchant,
            "amount": item.amount,
            "category": item.category,
            "is_anomaly": item.is_anomaly,
            "anomaly_score": item.anomaly_score,
            "is_unnecessary": item.is_unnecessary,
            "notes": item.notes,
        }
        for item in items
    ]


@app.delete("/transactions")
def clear_transactions(db: Session = Depends(get_db)):
    deleted = db.query(Transaction).delete()
    db.commit()
    return {"deleted": deleted}


@app.get("/budgets")
def list_budgets(db: Session = Depends(get_db)):
    return [
        {"category": item.category, "monthly_limit": item.monthly_limit}
        for item in db.query(BudgetLimit).all()
    ]


@app.post("/budgets")
def upsert_budget(payload: BudgetLimitIn, db: Session = Depends(get_db)):
    item = db.query(BudgetLimit).filter(BudgetLimit.category == payload.category).one_or_none()
    if item is None:
        item = BudgetLimit(category=payload.category, monthly_limit=payload.monthly_limit)
        db.add(item)
    else:
        item.monthly_limit = payload.monthly_limit
    db.commit()
    return {"category": item.category, "monthly_limit": item.monthly_limit}


def _tx_to_dict(item: Transaction) -> dict:
    return {
        "id": item.id,
        "date": item.date,
        "description": item.description,
        "merchant": item.merchant,
        "amount": item.amount,
        "category": item.category if item.category != "Uncategorized" else "",
        "is_anomaly": item.is_anomaly,
        "anomaly_score": item.anomaly_score,
        "is_unnecessary": item.is_unnecessary,
        "notes": item.notes,
    }


@app.post("/analyze")
def analyze(payload: AnalyzeRequest | None = None, db: Session = Depends(get_db)):
    payload = payload or AnalyzeRequest()
    items = db.query(Transaction).all()
    if not items:
        raise HTTPException(status_code=400, detail="Upload transactions before running analysis")
    limits = {row.category: row.monthly_limit for row in db.query(BudgetLimit).all()}
    result = run_expense_pipeline(
        {
            "transactions": [_tx_to_dict(item) for item in items],
            "user_limits": limits,
            "monthly_income": payload.monthly_income,
            "savings_goal": payload.savings_goal,
        }
    )
    by_id = {tx.get("id"): tx for tx in result.get("transactions") or []}
    for item in items:
        updated = by_id.get(item.id, {})
        item.category = updated.get("category") or item.category
        item.is_anomaly = bool(updated.get("is_anomaly"))
        item.anomaly_score = float(updated.get("anomaly_score") or 0)
        item.is_unnecessary = bool(updated.get("is_unnecessary"))
        item.notes = updated.get("notes") or ""
    summary = {
        "analysis": result.get("analysis") or {},
        "anomalies": result.get("anomalies") or [],
        "budget": result.get("budget") or {},
        "report": result.get("report") or {},
    }
    run = AnalysisRun(summary_json=json.dumps(summary), report_text=result.get("insights") or "")
    db.add(run)
    db.commit()
    return {"run_id": run.id, **summary}


@app.get("/reports/latest")
def latest_report(db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).first()
    if run is None:
        raise HTTPException(status_code=404, detail="No analysis has been run yet")
    return {
        "run_id": run.id,
        "created_at": run.created_at.isoformat(),
        "insights": run.report_text,
        **json.loads(run.summary_json or "{}"),
    }


@app.get("/anomalies")
def list_anomalies(db: Session = Depends(get_db)):
    items = db.query(Transaction).filter(Transaction.is_anomaly.is_(True)).order_by(Transaction.anomaly_score.desc()).all()
    return [
        {
            "id": item.id,
            "date": item.date,
            "description": item.description,
            "merchant": item.merchant,
            "amount": item.amount,
            "category": item.category,
            "anomaly_score": item.anomaly_score,
            "notes": item.notes,
        }
        for item in items
    ]
