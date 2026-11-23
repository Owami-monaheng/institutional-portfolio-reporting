"""Market data retrieval with refresh logging."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from config.portfolio_config import INSTRUMENTS, START_DATE, AS_OF_DATE

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LOG = ROOT / "data" / "processed" / "refresh_log.json"


def fetch_prices() -> pd.DataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    tickers = list(INSTRUMENTS)
    end = (pd.Timestamp(AS_OF_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")  # end is exclusive
    prices = yf.download(
        tickers, start=START_DATE, end=end, auto_adjust=True, progress=False
    )["Close"]

    warnings, coverage = [], {}
    for t in tickers:
        if t not in prices.columns or prices[t].dropna().empty:
            warnings.append(f"{t}: no data returned")
            continue
        s = prices[t].dropna()
        coverage[t] = {
            "first": str(s.index.min().date()),
            "last": str(s.index.max().date()),
            "rows": int(s.size),
        }
        missing = int(prices[t].isna().sum())
        if missing:
            warnings.append(f"{t}: {missing} missing days vs. combined calendar")

    # JSE quotes are in cents (ZAc) -> convert to rand
    for t, meta in INSTRUMENTS.items():
        if meta["ccy"] == "ZAc" and t in prices.columns:
            prices[t] = prices[t] / 100

    prices.to_csv(RAW / "prices.csv")
    LOG.write_text(json.dumps({
        "refreshed_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance (auto_adjust=True)",
               "start_date": START_DATE,
        "as_of_date": AS_OF_DATE,
        "coverage": coverage,
        "warnings": warnings,
    }, indent=2))
    return prices


if __name__ == "__main__":
    df = fetch_prices()
    print(df.tail())
    print(f"\n{df.shape[1]} instruments, {df.shape[0]} rows. See data/processed/refresh_log.json")