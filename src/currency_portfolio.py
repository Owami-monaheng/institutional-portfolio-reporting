"""Portfolio-level currency decomposition (Investigation C)."""
from pathlib import Path

import pandas as pd

from config.portfolio_config import PORTFOLIOS, INSTRUMENTS
from src.contribution_analysis import daily_contributions
from src.data_prep import clean_prices
from src.performance_metrics import total_return, cagr
from src.portfolio_analysis import portfolio_returns

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

USD_ASSETS = [t for t, m in INSTRUMENTS.items() if m["ccy"] == "USD" and m["type"] != "fx"]


def run():
    assets = pd.read_csv(PROC / "asset_returns_zar.csv", index_col=0, parse_dates=True)
    fx_level = clean_prices()["USDZAR=X"]
    fx = fx_level.pct_change().reindex(assets.index)       # daily USD/ZAR change (cleaned)

    # Same assets, with USD holdings measured in their own currency (rand held flat)
    assets_fx_flat = assets.copy()
    assets_fx_flat[USD_ASSETS] = (1 + assets[USD_ASSETS]).div(1 + fx, axis=0) - 1

    rows = []
    for pid, p in PORTFOLIOS.items():
        c, w = daily_contributions(assets, p["weights"])
        usd_cols = [t for t in c.columns if t in USD_ASSETS]
        other_cols = [t for t in c.columns if t not in USD_ASSETS]
        r_usd = (1 + assets[usd_cols]).div(1 + fx, axis=0) - 1

        usd_zar = c[usd_cols].sum().sum()
        usd_local = (w[usd_cols] * r_usd).sum().sum()
        actual = portfolio_returns(assets, p["weights"])
        flat = portfolio_returns(assets_fx_flat, p["weights"])

        rows.append({
            "portfolio": pid, "mandate": p["mandate"],
            "usd_asset_weight_avg": w[usd_cols].sum(axis=1).mean(),
            # compounded view (headline)
            "return_if_rand_flat": total_return(flat),
            "return_zar_actual": total_return(actual),
            "currency_drag_compounded": total_return(actual) - total_return(flat),
            "cagr_if_rand_flat": cagr(flat),
            "cagr_zar_actual": cagr(actual),
            # additive contribution view (composition)
            "usd_assets_in_usd": usd_local,
            "currency_effect_additive": usd_zar - usd_local,
            "usd_assets_in_zar": usd_zar,
            "zar_assets_and_synthetic": c[other_cols].sum().sum(),
        })

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "currency_exposure_by_portfolio.csv", index=False)
    fx_level.resample("ME").last().to_csv(PROC / "usdzar_monthly.csv")
    return out, fx_level


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    out, fx_level = run()
    f = lambda x: f"{x:.3f}"
    print(f"USD/ZAR: {fx_level.iloc[0]:.2f} -> {fx_level.iloc[-1]:.2f} "
          f"({fx_level.iloc[-1] / fx_level.iloc[0] - 1:+.1%}); "
          f"range {fx_level.min():.2f} to {fx_level.max():.2f} (low on {fx_level.idxmin().date()})\n")
    print("COMPOUNDED: what the rand move did to total return\n")
    print(out.iloc[:, :7].to_string(index=False, float_format=f))
    print("\nADDITIVE CONTRIBUTIONS: composition of return\n")
    print(out[["portfolio", "usd_assets_in_usd", "currency_effect_additive",
               "usd_assets_in_zar", "zar_assets_and_synthetic"]].to_string(index=False, float_format=f))