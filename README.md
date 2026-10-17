# Agentic AI-Based Intelligent Expense Analysis and Budget Planner

An autonomous, multi-agent personal finance management and budget planning system powered by **LangGraph**, **Google Gemini**, **scikit-learn**, **FastAPI**, and **Streamlit**.

Unlike traditional expense trackers that act merely as passive recording ledgers, this system orchestrates a workflow of 5 specialized AI agents to autonomously categorize expenses, identify spending patterns, flag billing anomalies and duplicate transactions, recommend realistic daily & category budgets, prevent budget deficits, and generate executive summaries.

---

## 🤖 Multi-Agent Architecture (LangGraph)

```mermaid
flowchart LR
    Data[Daily Log / Bank CSV] --> C[1. Categorization Agent]
    C --> S[2. Spending Analysis Agent]
    S --> A[3. Anomaly Detection Agent]
    A --> B[4. Budget Planning Agent]
    B --> R[5. Report Generation Agent]
    R --> UI[Streamlit UI / FastAPI REST API]
```

1. **Transaction Categorization Agent**: Autonomously parses raw descriptions and standardizes expenses into categories (*Food & Dining, Groceries, Shopping, Travel, Bills, Housing, Healthcare, Entertainment*).
2. **Spending Analysis Agent**: Computes month-over-month trajectories, category distributions, merchant aggregations, and isolates discretionary/unnecessary expenditures.
3. **Anomaly Detection Agent**: Unsupervised outlier analysis & duplicate charge detection with plain-English contextual explanations and verification steps.
4. **Budget Planning Agent**: Dynamic deficit engine calculating daily spending allowance, category budget recommendations, net cash flows, and deficit alerts when user limits exceed income.
5. **Report Generation Agent**: Formulates concise financial briefings, debt-reduction advice, and automated Matplotlib visual representations.

---

## 🛠️ Tech Stack

- **Language:** Python 3.12+ / 3.14
- **Multi-Agent Orchestration:** LangGraph, LangChain Core
- **AI & Machine Learning:** Google Gemini API (`google-generativeai`), scikit-learn
- **Data & Visuals:** Pandas, NumPy, Matplotlib
- **Backend Services:** FastAPI, Uvicorn, Pydantic, SQLAlchemy, SQLite
- **Interactive Frontend:** Streamlit
- **Testing:** Pytest

---

## 🚀 Quickstart

### 1. Clone & Environment Setup
```bash
git clone https://github.com/Srishtiops/agentic-budget-planner.git
cd agentic-budget-planner
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

*(Optional: Set `GEMINI_API_KEY` in `.env` for generative AI insights. The system functions deterministically even without an API key).*

### 2. Run the Interactive Dashboard
```bash
streamlit run dashboard/streamlit_app.py
```
Open **http://127.0.0.1:8501** in your browser.
- **Daily Budget & Tracker**: Log today's expenses and track daily spending allowances.
- **Monthly Budget & Deficit Engine**: Real-time deficit warnings if planned category limits exceed monthly income.
- **AI Financial Intelligence**: Run the 5 autonomous agents across categorized spending, anomalies, and AI executive reports.

### 3. Run the FastAPI Backend
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive API Documentation: **http://127.0.0.1:8000/docs**
- Health endpoint: `GET http://127.0.0.1:8000/health`

---

## 🧪 Testing

Execute the automated test suite verifying ingestion, categorization, anomaly detection, budget planning, and REST endpoints:
```bash
pytest -v
```

---

## 📄 Project Documentation

- **Full Project Report (Word Document):** [`Agentic_AI_Project_Report.docx`](Agentic_AI_Project_Report.docx)
- **HTML Web Preview:** [`Agentic_AI_Project_Report.html`](Agentic_AI_Project_Report.html)
- **Evaluation Dataset Details:** [`sample_data/DATASETS.md`](sample_data/DATASETS.md)
