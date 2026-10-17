from pydantic import BaseModel, Field


class TransactionIn(BaseModel):
    date: str
    description: str
    merchant: str = ""
    amount: float


class BudgetLimitIn(BaseModel):
    category: str
    monthly_limit: float = Field(gt=0)


class AnalyzeRequest(BaseModel):
    monthly_income: float | None = None
    savings_goal: float | None = None
