"""Run the full reporting pipeline in order.

Usage:
    python -m src.run_pipeline                  # refresh market data, then rebuild everything
    python -m src.run_pipeline --skip-refresh   # rebuild from the data already downloaded
"""
import sys
import time

from src import (market_data, synthetic_data, currency_analysis, portfolio_analysis,
                 contribution_analysis, currency_portfolio, exception_analysis, report_pack)

STEPS = [
    ("Refresh market data", market_data.fetch_prices),
    ("Build synthetic holdings", synthetic_data.build),
    ("Clean prices and compute ZAR returns", currency_analysis.build_asset_returns_zar),
    ("Portfolio and benchmark performance", portfolio_analysis.run),
    ("Contribution and concentration", contribution_analysis.run),
    ("Currency decomposition", currency_portfolio.run),
    ("Rolling metrics and exception flags", exception_analysis.run),
    ("Generate PDF reports", report_pack.main),
]


def main():
    skip_refresh = "--skip-refresh" in sys.argv
    for name, fn in STEPS:
        if skip_refresh and fn is market_data.fetch_prices:
            print(f"- {name}: skipped")
            continue
        t0 = time.time()
        fn()
        print(f"- {name}: done ({time.time() - t0:.1f}s)")
    print("\nOutputs written to data/processed/. Launch the dashboard: streamlit run dashboard.py")


if __name__ == "__main__":
    main()