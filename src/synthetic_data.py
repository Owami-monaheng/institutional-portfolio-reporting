"""Generate synthetic portfolio holdings and allocations from config."""
from pathlib import Path

import pandas as pd

from config.portfolio_config import PORTFOLIOS, INSTRUMENTS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "synthetic"
STARTING_VALUE_ZAR = 10_000_000  # hypothetical, per portfolio

# Classification assumptions (documented in assumptions.md)
META = {
    "AAPL":     ("Equity",       "International", "Technology"),
    "MSFT":     ("Equity",       "International", "Technology"),
    "^GSPC":    ("Equity",       "International", "Broad market (index proxy)"),
    "^NDX":     ("Equity",       "International", "Technology (index proxy)"),
    "NPN.JO":   ("Equity",       "South Africa",  "Consumer / Internet"),
    "SBK.JO":   ("Equity",       "South Africa",  "Financials"),
    "GC=F":     ("Commodity",    "International", "Gold"),
    "SA_BONDS": ("Fixed income", "South Africa",  "Government bonds (synthetic)"),
    "SA_CASH":  ("Cash",         "South Africa",  "Cash (synthetic)"),
}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid, p in PORTFOLIOS.items():
        for tkr, w in p["weights"].items():
            asset_class, region, sector = META[tkr]
            rows.append({
                "portfolio": pid,
                "mandate": p["mandate"],
                "ticker": tkr,
                "name": INSTRUMENTS.get(tkr, {}).get("name", tkr),
                "asset_class": asset_class,
                "region": region,
                "sector": sector,
                "weight": w,
                "start_value_zar": w * STARTING_VALUE_ZAR,
                "is_synthetic": tkr.startswith("SA_"),
            })
    holdings = pd.DataFrame(rows)
    holdings.to_csv(OUT / "portfolio_holdings.csv", index=False)

    alloc = (holdings.groupby(["portfolio", "mandate", "asset_class", "region"],
                              as_index=False)["weight"].sum())
    alloc.to_csv(OUT / "portfolio_allocations.csv", index=False)
    return holdings, alloc


if __name__ == "__main__":
    h, a = build()
    print(a.to_string(index=False))