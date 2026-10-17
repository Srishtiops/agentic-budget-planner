from langgraph.graph import END, START, StateGraph

from app.agents.anomaly_detection import detect_anomalies
from app.agents.budget_planning import plan_budget
from app.agents.categorization import categorize_transactions
from app.agents.report_generation import generate_report
from app.agents.spending_analysis import analyze_spending
from app.agents.state import ExpenseState


def build_graph():
    graph = StateGraph(ExpenseState)
    graph.add_node("categorize", categorize_transactions)
    graph.add_node("analyze", analyze_spending)
    graph.add_node("detect_anomalies", detect_anomalies)
    graph.add_node("plan_budget", plan_budget)
    graph.add_node("generate_report", generate_report)
    graph.add_edge(START, "categorize")
    graph.add_edge("categorize", "analyze")
    graph.add_edge("analyze", "detect_anomalies")
    graph.add_edge("detect_anomalies", "plan_budget")
    graph.add_edge("plan_budget", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()


_PIPELINE = None


def run_expense_pipeline(payload: dict) -> dict:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = build_graph()
    return _PIPELINE.invoke(payload)
