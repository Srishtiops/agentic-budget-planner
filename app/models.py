from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(String(512))
    merchant: Mapped[str] = mapped_column(String(256), default="")
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(64), default="Uncategorized")
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_unnecessary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(64), unique=True)
    monthly_limit: Mapped[float] = mapped_column(Float)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    report_text: Mapped[str] = mapped_column(Text, default="")
