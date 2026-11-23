# Institutional Portfolio Reporting

A reproducible reporting pipeline for a **simulated** private wealth manager (Meridian Private Wealth & Capital).
It consolidates market data, measures portfolio performance and risk in ZAR, separates currency effects,
flags exceptions for adviser review, and generates a dashboard and PDF reports.

**Scope:** reporting support only. No investment recommendations or advice.

## What it produces

- Streamlit monitoring dashboard (`dashboard.py`)
- Quarterly reporting pack and one-page executive summary (`reports/`)
- Documented methodology, assumptions and data dictionary (`documentation/`)

## Run it

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.run_pipeline          # refresh data, recalculate, regenerate reports
streamlit run dashboard.py
```

Use `python -m src.run_pipeline --skip-refresh` to rebuild from already-downloaded data.
The analysis window is pinned in `config/portfolio_config.py` (`START_DATE`, `AS_OF_DATE`),
so results do not change with the day you run it.

## Method highlights

- Real prices from Yahoo Finance; **synthetic** holdings, weights, and bond/cash returns.
- ZAR returns compound the USD return and the USD/ZAR change; currency drag is shown against a
  rand-held-flat counterfactual.
- Contribution, concentration (effective holdings), rolling returns, drawdown, volatility, Sharpe
  against an assumed 7% ZAR cash rate.
- Data-quality controls: refresh log, gap handling, four documented source-data corrections
  (bad ticks found by an exceptions report), and a reviewed list of large moves.
- Benchmarks mirror each mandate's asset-class weights using index proxies.

## Limitations

- Holdings are hypothetical and bond/cash sleeves are assumed, so results for B and C partly reflect assumptions.
- Exception thresholds are illustrative and would need agreeing with advisers.
- Index tickers are proxies with no look-through; technology exposure is a lower bound.
- Not investment advice.
