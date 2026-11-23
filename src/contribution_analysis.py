"""Contribution and concentration analysis (Investigations A and B)."""
from pathlib import Path

import numpy as np
import pandas as pd

from config.portfolio_config import PORTFOLIOS
from src.portfolio_analysis import portfolio_returns

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
HOLD = ROOT / "data" / "synthetic" / "portfolio_holdings.csv"


def daily_contributions(asset_rets: pd.DataFrame, weights: dict):
    """Per-holding daily contribution (start-of-day weight x return) and the weight path."""
    r = asset_rets[list(weights)]
    target = pd.Series(weights)
    w, prev_q, contrib, wpath = target.copy(), None, [], []
    for dt, row in r.iterrows():
        q = (dt.year, dt.quarter)
        if prev_q is not None and q != prev_q:
            w = target.copy()                       # quarterly rebalance, same as portfolio_returns
        wpath.append(w.values.copy())
        c = w * row
        contrib.append(c.values)
        pr = float(c.sum())
        w = w * (1 + row) / (1 + pr)
        prev_q = q
    return (pd.DataFrame(contrib, index=r.index, columns=r.columns),
            pd.DataFrame(wpath, index=r.index, columns=r.columns))


def run():
    assets = pd.read_csv(PROC / "asset_returns_zar.csv", index_col=0, parse_dates=True)
    holdings = pd.read_csv(HOLD)
    contrib_rows, conc_rows, monthly = [], [], {}

    for pid, p in PORTFOLIOS.items():
        c, w = daily_contributions(assets, p["weights"])
        # Integrity check: contributions must add up to the portfolio return used elsewhere
        assert np.allclose(c.sum(axis=1), portfolio_returns(assets, p["weights"])), \
            f"Portfolio {pid}: contributions do not reconcile to portfolio returns"

        total = c.sum().sum()
        for t in c.columns:
            contrib_rows.append({
                "portfolio": pid, "ticker": t,
                "avg_weight": w[t].mean(),
                "contribution": c[t].sum(),          # sum of daily weighted returns
                "share_of_total": c[t].sum() / total,
            })

        h = holdings[holdings.portfolio == pid].set_index("ticker")
        top5 = w.apply(lambda row: row.nlargest(5).sum(), axis=1)
        hhi = (w ** 2).sum(axis=1)
        tech = w[[t for t in w.columns if str(h.loc[t, "sector"]).startswith("Technology")]].sum(axis=1)
        intl = w[[t for t in w.columns if h.loc[t, "region"] == "International"]].sum(axis=1)
        market = [t for t in w.columns if not bool(h.loc[t, "is_synthetic"])]
        corr = assets[market].corr().values
        avg_corr = corr[np.triu_indices(len(market), 1)].mean()

        conc_rows.append({
            "portfolio": pid, "top5_start": top5.iloc[0], "top5_avg": top5.mean(),
            "top5_max": top5.max(), "top5_end": top5.iloc[-1],
            "largest_holding_end": w.iloc[-1].idxmax(), "largest_weight_end": w.iloc[-1].max(),
            "hhi_end": hhi.iloc[-1], "tech_share_end": tech.iloc[-1],
            "intl_share_end": intl.iloc[-1], "avg_pairwise_corr": avg_corr,
        })
        monthly[f"{pid}_top5"] = top5.resample("ME").last()
        monthly[f"{pid}_intl"] = intl.resample("ME").last()

    contrib_df, conc_df = pd.DataFrame(contrib_rows), pd.DataFrame(conc_rows)
    contrib_df.to_csv(PROC / "contribution_analysis.csv", index=False)
    conc_df.to_csv(PROC / "concentration_summary.csv", index=False)
    pd.DataFrame(monthly).to_csv(PROC / "concentration_monthly.csv")
    return contrib_df, conc_df


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    contrib_df, conc_df = run()
    fmt = lambda x: f"{x:.3f}"
    print("CONTRIBUTION (sum of daily weighted returns; shares sum to 1.0 per portfolio)\n")
    print(contrib_df.to_string(index=False, float_format=fmt))
    print("\nCONCENTRATION\n")
    print(conc_df.to_string(index=False, float_format=fmt))