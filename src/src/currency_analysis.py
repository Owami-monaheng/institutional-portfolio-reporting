"""Convert USD assets to ZAR and decompose returns (Investigation C)."""
from pathlib import Path

import pandas as pd  # type: ignore[import-unresolved]

from config.portfolio_config import INSTRUMENTS
from src.data_prep import clean_prices, synthetic_returns

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed"


def build_asset_returns_zar():
    px = clean_prices()
    local = px.pct_change().dropna()          # returns in each asset's own currency
    fx = local["USDZAR=X"]                    # rand per dollar: up = rand weaker

    zar = pd.DataFrame(index=local.index)
    for t, m in INSTRUMENTS.items():
        if m["type"] == "fx":
            continue
        if m["ccy"] == "USD":
            zar[t] = (1 + local[t]) * (1 + fx) - 1     # compound, never add
        else:
            zar[t] = local[t]                           # JSE assets already in ZAR

    zar = zar.join(synthetic_returns(zar.index))
    OUT.mkdir(parents=True, exist_ok=True)
    zar.to_csv(OUT / "asset_returns_zar.csv")

    # Decomposition over the full window: USD return vs. currency vs. combined ZAR
    cum = lambda s: (1 + s).prod() - 1
    rows = []
    for t, m in INSTRUMENTS.items():
        if m["ccy"] == "USD" and m["type"] != "fx":
            usd, z = cum(local[t]), cum(zar[t])
            rows.append({
                "ticker": t,
                "usd_return": usd,
                "usdzar_change": cum(fx),
                "zar_return": z,
                "currency_effect": z - usd,    # includes the cross term
            })
    decomp = pd.DataFrame(rows)
    decomp.to_csv(OUT / "currency_decomposition.csv", index=False)
    return zar, decomp


if __name__ == "__main__":
    zar, decomp = build_asset_returns_zar()
    print(f"Window: {zar.index.min().date()} to {zar.index.max().date()}, {len(zar)} daily returns\n")
    print(decomp.to_string(index=False, float_format=lambda x: f"{x:.1%}"))