"""Rolling returns, benchmark deviation and exception flags (Investigation D, Q5)."""
from pathlib import Path

import numpy as np
import pandas as pd

from config.portfolio_config import PORTFOLIOS, SYNTHETIC
from src.contribution_analysis import daily_contributions

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

WINDOW = 63                       # ~one quarter of trading days
UNDERPERFORM_LIMIT = -0.05        # rolling-quarter return minus benchmark
MAX_SINGLE_WEIGHT = 0.30
# ILLUSTRATIVE reporting thresholds, to be agreed with the adviser team (see assumptions.md)
MANDATE_LIMITS = {
    "A": {"max_drawdown": -0.12, "rolling_vol": 0.22},
    "B": {"max_drawdown": -0.08, "rolling_vol": 0.12},
    "C": {"max_drawdown": -0.04, "rolling_vol": 0.06},
}


def rolling_return(r: pd.Series) -> pd.Series:
    return np.expm1(np.log1p(r).rolling(WINDOW).sum())


def drawdown(r: pd.Series) -> pd.Series:
    cum = (1 + r).cumprod()
    return cum / cum.cummax() - 1


def run():
    assets = pd.read_csv(PROC / "asset_returns_zar.csv", index_col=0, parse_dates=True)
    rets = pd.read_csv(PROC / "portfolio_returns.csv", index_col=0, parse_dates=True)

    rolling, flags = {}, []
    for pid, p in PORTFOLIOS.items():
        port, bench = rets[f"Portfolio {pid}"], rets[f"Benchmark {pid}"]
        rr_p, rr_b = rolling_return(port), rolling_return(bench)
        excess = rr_p - rr_b
        rvol = port.rolling(WINDOW).std() * np.sqrt(252)
        dd = drawdown(port)
        _, w = daily_contributions(assets, p["weights"])
        securities = [t for t in w.columns if t not in SYNTHETIC]   # sleeves are not single names
        maxw = w[securities].max(axis=1)
        lim = MANDATE_LIMITS[pid]

        rolling.update({
            f"{pid}_rolling_return": rr_p, f"{pid}_rolling_benchmark": rr_b,
            f"{pid}_rolling_excess": excess, f"{pid}_rolling_vol": rvol, f"{pid}_drawdown": dd,
        })

        rules = [
            (f"Rolling {WINDOW}d return trails benchmark by > {abs(UNDERPERFORM_LIMIT):.0%}",
             excess, excess < UNDERPERFORM_LIMIT, "min"),
            (f"Drawdown deeper than mandate limit ({lim['max_drawdown']:.0%})",
             dd, dd < lim["max_drawdown"], "min"),
            (f"Rolling volatility above mandate limit ({lim['rolling_vol']:.0%})",
             rvol, rvol > lim["rolling_vol"], "max"),
            (f"Single holding above {MAX_SINGLE_WEIGHT:.0%} of portfolio",
             maxw, maxw > MAX_SINGLE_WEIGHT, "max"),
        ]
        for name, series, mask, worse in rules:
            mask = mask.fillna(False)
            hit = series[mask]
            flags.append({
                "portfolio": pid,
                "rule": name,
                "days_breached": int(mask.sum()),
                "first_breach": str(hit.index.min().date()) if mask.any() else "",
                "last_breach": str(hit.index.max().date()) if mask.any() else "",
                "worst_value": (hit.min() if worse == "min" else hit.max()) if mask.any() else np.nan,
                "active_at_period_end": bool(mask.iloc[-1]),
            })

    pd.DataFrame(rolling).to_csv(PROC / "rolling_metrics.csv")
    flags_df = pd.DataFrame(flags)
    flags_df.to_csv(PROC / "exception_flags.csv", index=False)
    return flags_df


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 70)
    print(run().to_string(index=False, float_format=lambda x: f"{x:.3f}"))