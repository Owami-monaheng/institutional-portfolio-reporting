"""Clean raw prices and generate synthetic sleeve returns."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config.portfolio_config import SYNTHETIC, INSTRUMENTS, KNOWN_DATA_ERRORS, VERIFIED_MOVES

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "prices.csv"
LOG = ROOT / "data" / "processed" / "refresh_log.json"

MAX_FFILL_DAYS = 5      # fill market-holiday gaps up to this many days
TRADING_DAYS = 252
SEED = 42               # fixed seed so synthetic series are reproducible

# Daily moves above these are reported as exceptions for review (not auto-corrected)
MOVE_THRESHOLDS = {"equity": 0.15, "equity_index": 0.08, "commodity": 0.08, "fx": 0.03}


def clean_prices() -> pd.DataFrame:
    """Weekdays only; trim stale tail; blank confirmed errors; forward-fill short gaps."""
    px = pd.read_csv(RAW, index_col=0, parse_dates=True).sort_index()
    rows_raw = len(px)

    px = px[px.index.dayofweek < 5]                           # drop weekend FX-only rows
    px = px.loc[:px.apply(pd.Series.last_valid_index).min()]  # no stale trailing prices

    for e in KNOWN_DATA_ERRORS:                               # confirmed bad ticks -> NaN
        ts = pd.Timestamp(e["date"])
        if ts in px.index:
            px.loc[ts, e["ticker"]] = np.nan

    na_before = int(px.isna().sum().sum())
    px = px.ffill(limit=MAX_FFILL_DAYS)
    cells_filled = na_before - int(px.isna().sum().sum())

    rows_before_drop = len(px)
    px = px.dropna()

    exceptions = []                                           # unusual moves, for review
    rets = px.pct_change().dropna()
    for t, m in INSTRUMENTS.items():
        lim = MOVE_THRESHOLDS[m["type"]]
        for d, v in rets[t][rets[t].abs() > lim].items():
            exceptions.append({"ticker": t, "date": str(d.date()),
                               "move": round(float(v), 4), "threshold": lim,
                               "status": VERIFIED_MOVES.get(f"{t}|{d.date()}", "OPEN - review")})
    info = {
        "rows_raw": rows_raw,
        "rows_clean": len(px),
        "rows_dropped_after_fill": rows_before_drop - len(px),
        "cells_forward_filled": cells_filled,
        "max_ffill_days": MAX_FFILL_DAYS,
        "clean_start": str(px.index.min().date()),
        "clean_end": str(px.index.max().date()),
        "known_errors_corrected": KNOWN_DATA_ERRORS,
        "move_exceptions": exceptions,
    }
    if LOG.exists():
        log = json.loads(LOG.read_text())
        log["cleaning"] = info
        LOG.write_text(json.dumps(log, indent=2))
    return px


def synthetic_returns(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily returns for SYNTHETIC sleeves. Assumed, NOT market observations."""
    rng = np.random.default_rng(SEED)
    out = {}
    for name, p in SYNTHETIC.items():
        daily_mu = (1 + p["annual_return"]) ** (1 / TRADING_DAYS) - 1
        daily_sd = p["annual_vol"] / np.sqrt(TRADING_DAYS)
        noise = rng.normal(0, daily_sd, len(index)) if daily_sd > 0 else np.zeros(len(index))
        noise = noise - noise.mean()        # realised mean return matches the assumption
        out[name] = daily_mu + noise
    return pd.DataFrame(out, index=index)