"""Case-study inputs. All weights are HYPOTHETICAL, not recommendations."""

REPORTING_BASE_CURRENCY = "ZAR"
HISTORY_YEARS = 3
START_DATE = "2023-11-21"   # first price date of the verified dataset
AS_OF_DATE = "2026-11-19"   # last date verified across all instruments
RISK_FREE_RATE = 0.0   # placeholder; document the choice in assumptions.md
REBALANCING = "quarterly_to_target"

INSTRUMENTS = {
    "^GSPC":    {"name": "S&P 500",       "ccy": "USD", "type": "equity_index"},
    "^NDX":     {"name": "Nasdaq 100",    "ccy": "USD", "type": "equity_index"},
    "AAPL":     {"name": "Apple",         "ccy": "USD", "type": "equity"},
    "MSFT":     {"name": "Microsoft",     "ccy": "USD", "type": "equity"},
    "NPN.JO":   {"name": "Naspers",       "ccy": "ZAc", "type": "equity"},   # JSE quotes in cents
    "SBK.JO":   {"name": "Standard Bank", "ccy": "ZAc", "type": "equity"},
     "STX40.JO": {"name": "Satrix 40 ETF", "ccy": "ZAc", "type": "equity_index"},   # JSE Top 40 proxy (total return)
    "GC=F":     {"name": "Gold futures",  "ccy": "USD", "type": "commodity"},
    "USDZAR=X": {"name": "USD/ZAR",       "ccy": "FX",  "type": "fx"},
}

# Synthetic sleeves: NOT market observations
SYNTHETIC = {
    "SA_BONDS": {"annual_return": 0.09,  "annual_vol": 0.06},
    "SA_CASH":  {"annual_return": 0.07,  "annual_vol": 0.00},
}

# Benchmarks mirror each portfolio's asset-class weights using index proxies:
# international equity -> US indices, SA equity -> Satrix 40 (JSE Top 40 proxy),
# gold -> gold futures, bonds and cash -> the same synthetic sleeves as the portfolio.
PORTFOLIOS = {
    "A": {"mandate": "Growth",
          "benchmark": {"^NDX": 0.35, "^GSPC": 0.35, "STX40.JO": 0.15, "GC=F": 0.05, "SA_CASH": 0.10},
          "weights": {"AAPL": 0.25, "MSFT": 0.25, "^GSPC": 0.20, "NPN.JO": 0.10,
                      "SBK.JO": 0.05, "GC=F": 0.05, "SA_CASH": 0.10}},
    "B": {"mandate": "Balanced",
          "benchmark": {"^GSPC": 0.30, "STX40.JO": 0.25, "GC=F": 0.05, "SA_BONDS": 0.25, "SA_CASH": 0.15},
          "weights": {"^GSPC": 0.20, "^NDX": 0.10, "NPN.JO": 0.10, "SBK.JO": 0.15,
                      "GC=F": 0.05, "SA_BONDS": 0.25, "SA_CASH": 0.15}},
    "C": {"mandate": "Income & Preservation",
          "benchmark": {"^GSPC": 0.10, "STX40.JO": 0.10, "GC=F": 0.10, "SA_BONDS": 0.40, "SA_CASH": 0.30},
          "weights": {"^GSPC": 0.10, "SBK.JO": 0.10, "GC=F": 0.10, "SA_BONDS": 0.40, "SA_CASH": 0.30}},
}

for k, p in PORTFOLIOS.items():
    assert abs(sum(p["weights"].values()) - 1) < 1e-9, f"Portfolio {k} weights != 100%"

# Confirmed source-data errors. Each is blanked out so the prior close carries forward.
KNOWN_DATA_ERRORS = [
    {"ticker": "SBK.JO", "date": "2025-04-25",
     "issue": "Price of R2.29 vs ~R228 either side (unit error in source data)",
     "treatment": "Blanked; previous close carried forward"},
    {"ticker": "USDZAR=X", "date": "2024-11-15",
     "issue": "Rate of 14.86 vs ~18.2 either side (bad tick; reverses next trading day)",
     "treatment": "Blanked; previous close carried forward"},
    {"ticker": "USDZAR=X", "date": "2025-01-15",
     "issue": "Rate of 16.50 vs ~18.9 either side (bad tick; reverses next trading day)",
     "treatment": "Blanked; previous close carried forward"},
    {"ticker": "USDZAR=X", "date": "2025-01-17",
     "issue": "Rate of 15.43 vs ~18.7 either side (bad tick; reverses next trading day)",
     "treatment": "Blanked; previous close carried forward"},
]

# Large moves checked against the surrounding prices and judged genuine (not data errors).
# Keys are "TICKER|YYYY-MM-DD". Status records what was verified, not a cause.
VERIFIED_MOVES = {
    "^GSPC|2025-04-09": "Checked: broad market move across US indices",
    "^NDX|2025-04-09": "Checked: broad market move across US indices",
    "AAPL|2025-04-09": "Checked: broad market move across US indices",
    "MSFT|2026-07-30": "Checked: step persisted; stock-specific (Nasdaq 100 +3.4% same day)",
    "NPN.JO|2023-12-22": "Checked: sharp dip, partial rebound within a week; not a data error",
    "GC=F|2026-01-30": "Checked: step persisted, partial bounce; not a data error",
}