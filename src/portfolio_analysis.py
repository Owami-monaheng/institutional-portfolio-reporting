"""Portfolio and benchmark returns (ZAR), with quarterly rebalancing."""
from pathlib import Path

import pandas as pd

from config.portfolio_config import PORTFOLIOS, SYNTHETIC
from src import performance_metrics as pm

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RF = SYNTHETIC["SA_CASH"]["annual_return"]   # ZAR cash proxy (assumed 7%) as the risk-free rate


def portfolio_returns(asset_rets: pd.DataFrame, weights: dict) -> pd.Series:
    """Daily return with weights drifting between quarterly resets to target."""
    r = asset_rets[list(weights)]
    target = pd.Series(weights)
    w, prev_q, out = target.copy(), None, []
    for dt, row in r.iterrows():
        q = (dt.year, dt.quarter)
        if prev_q is not None and q != prev_q:
            w = target.copy()                      # quarterly rebalance
        pr = float((w * row).sum())
        out.append(pr)
        w = w * (1 + row) / (1 + pr)               # drift
        prev_q = q
    return pd.Series(out, index=r.index)


def run():
    assets = pd.read_csv(PROC / "asset_returns_zar.csv", index_col=0, parse_dates=True)
    rets, rows = {}, []
    for pid, p in PORTFOLIOS.items():
        port = portfolio_returns(assets, p["weights"])
        bench = portfolio_returns(assets, p["benchmark"])
        rets[f"Portfolio {pid}"], rets[f"Benchmark {pid}"] = port, bench
        m = pm.summary(port, RF)
        te = (port - bench).std() * (pm.TD ** 0.5)
        rows.append({"portfolio": pid, "mandate": p["mandate"], **m,
                     "benchmark_cagr": pm.cagr(bench),
                     "excess_cagr": m["cagr"] - pm.cagr(bench),
                     "tracking_error": te})
    pd.DataFrame(rets).to_csv(PROC / "portfolio_returns.csv")
    summ = pd.DataFrame(rows)
    summ.to_csv(PROC / "performance_summary.csv", index=False)
    return summ


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(run().to_string(index=False, float_format=lambda x: f"{x:.3f}"))