# Benchmark Dataset for Testing and Evaluation

Primary file used for evaluation: `sample_data/transactions.csv`  

Per the project specification (*Section 6: Testing and Evidence*):
> "The system will be tested using sample transaction datasets containing normal expenses, overspending, duplicate entries, and unusual transactions. The results will be evaluated by checking transaction categorization accuracy, verifying flagged anomalies against known test cases, and comparing recommended budgets with user-defined limits."

### Benchmark Composition (`sample_data/transactions.csv`):
- **289 total transactions** covering multiple months
- **Normal expenses**: Groceries, dining, transportation, utility bills
- **Overspending spikes**: Large electronics, high shopping expenditures
- **Duplicate charges**: Multiple identical transactions within short windows
- **Outliers / Anomalies**: Extreme transaction values designed to evaluate the **scikit-learn Isolation Forest** model
