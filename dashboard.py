"""Portfolio Monitoring Dashboard. Run: streamlit run dashboard.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
PROC = ROOT / "data" / "processed"
HOLD = ROOT / "data" / "synthetic" / "portfolio_holdings.csv"

st.set_page_config(page_title="Portfolio Monitoring", layout="wide")

REQUIRED = ["portfolio_returns.csv", "performance_summary.csv", "contribution_analysis.csv",
            "concentration_summary.csv", "rolling_metrics.csv", "currency_exposure_by_portfolio.csv",
            "usdzar_monthly.csv", "exception_flags.csv", "asset_returns_zar.csv", "refresh_log.json"]
missing = [f for f in REQUIRED if not (PROC / f).exists()]
if missing:
    st.error("Outputs not found: " + ", ".join(missing))
    st.write("Generate them from the project root:")
    st.code("python -m src.run_pipeline")
    st.stop()


@st.cache_data
def load():
    rd = lambda f, **k: pd.read_csv(PROC / f, **k)
    return dict(
        rets=rd("portfolio_returns.csv", index_col=0, parse_dates=True),
        perf=rd("performance_summary.csv"),
        contrib=rd("contribution_analysis.csv"),
        conc=rd("concentration_summary.csv"),
        roll=rd("rolling_metrics.csv", index_col=0, parse_dates=True),
        ccy=rd("currency_exposure_by_portfolio.csv"),
        fx=rd("usdzar_monthly.csv", index_col=0, parse_dates=True),
        flags=rd("exception_flags.csv"),
        assets=rd("asset_returns_zar.csv", index_col=0, parse_dates=True),
        holdings=pd.read_csv(HOLD),
        log=json.loads((PROC / "refresh_log.json").read_text()),
    )


D = load()

st.title("Portfolio Performance & Risk Monitoring")
st.caption("SIMULATION. Holdings and weights are synthetic; SA bond and cash returns are assumed, "
           "not observed. Market prices are real (Yahoo Finance). Reporting only: not investment advice.")

pid = st.sidebar.radio("Portfolio", ["A", "B", "C"], format_func=lambda x: f"Portfolio {x}")
row = D["perf"].set_index("portfolio").loc[pid]
st.sidebar.markdown(f"**Mandate:** {row['mandate']}")
st.sidebar.caption(f"Data window: {D['rets'].index.min().date()} to {D['rets'].index.max().date()}")
st.sidebar.caption("Sharpe uses an assumed 7% ZAR cash rate as the risk-free rate.")

k = st.columns(6)
k[0].metric("Total return", f"{row.total_return:.1%}")
k[1].metric("CAGR", f"{row.cagr:.1%}", f"{row.excess_cagr * 100:+.1f} pts vs bench")
k[2].metric("Volatility", f"{row.ann_vol:.1%}")
k[3].metric("Max drawdown", f"{row.max_drawdown:.1%}")
k[4].metric("Sharpe", f"{row.sharpe:.2f}")
k[5].metric("Worst day", f"{row.worst_day:.1%}")

tabs = st.tabs(["Performance", "Contribution", "Risk", "Currency", "Concentration",
                "Exceptions & data quality"])

with tabs[0]:
    cols = [f"Portfolio {pid}", f"Benchmark {pid}"]
    cum = (1 + D["rets"][cols]).cumprod() - 1
    st.plotly_chart(px.line(cum, title="Cumulative return (ZAR)",
                            labels={"value": "Return", "index": "", "variable": ""}),
                    use_container_width=True)
    freq = st.radio("Period", ["Monthly", "Quarterly"], horizontal=True)
    per = (1 + D["rets"][cols]).resample("ME" if freq == "Monthly" else "QE").prod() - 1
    st.plotly_chart(px.bar(per, barmode="group", title=f"{freq} returns",
                           labels={"value": "Return", "index": "", "variable": ""}),
                    use_container_width=True)
    st.subheader("All portfolios")
    st.dataframe(D["perf"].round(3), hide_index=True, use_container_width=True)

with tabs[1]:
    c = D["contrib"].query("portfolio == @pid").sort_values("contribution")
    fig = px.bar(c, x="contribution", y="ticker", orientation="h",
                 text=c["share_of_total"].map("{:.0%}".format),
                 title="Contribution to return (sum of daily weighted returns); label = share of total")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("SA_BONDS and SA_CASH are synthetic sleeves: their contribution reflects assumptions.")

with tabs[2]:
    r = D["roll"]
    st.plotly_chart(px.line(r[f"{pid}_rolling_excess"], title="Rolling 63-day return minus benchmark"),
                    use_container_width=True)
    st.plotly_chart(px.line(r[f"{pid}_rolling_vol"], title="Rolling 63-day annualised volatility"),
                    use_container_width=True)
    st.plotly_chart(px.line(r[f"{pid}_drawdown"], title="Drawdown from peak"),
                    use_container_width=True)

with tabs[3]:
    cc = D["ccy"].set_index("portfolio").loc[pid]
    a, b, c3 = st.columns(3)
    a.metric("Return if USD/ZAR held flat", f"{cc.return_if_rand_flat:.1%}")
    b.metric("Actual ZAR return", f"{cc.return_zar_actual:.1%}")
    c3.metric("Currency drag", f"{cc.currency_drag_compounded * 100:+.1f} pts")
    st.write(f"Average USD-asset weight: **{cc.usd_asset_weight_avg:.0%}**")
    st.plotly_chart(px.line(D["fx"].iloc[:, 0], title="USD/ZAR, month-end (higher = weaker rand)"),
                    use_container_width=True)
    st.dataframe(D["ccy"].round(3), hide_index=True, use_container_width=True)
    st.caption("Compounded view is the headline. The additive view understates the drag because "
               "it ignores compounding.")

with tabs[4]:
    cn = D["conc"].set_index("portfolio").loc[pid]
    a, b, c3, d = st.columns(4)
    a.metric("Largest holding", f"{cn.largest_holding_end} {cn.largest_weight_end:.0%}")
    b.metric("Effective no. of holdings", f"{1 / cn.hhi_end:.1f}")
    c3.metric("Technology share", f"{cn.tech_share_end:.0%}")
    d.metric("International share", f"{cn.intl_share_end:.0%}")
    st.dataframe(D["holdings"].query("portfolio == @pid")[
        ["ticker", "name", "asset_class", "region", "sector", "weight", "is_synthetic"]],
        hide_index=True, use_container_width=True)
    mkt = [c for c in D["assets"].columns if not c.startswith("SA_")]
    st.plotly_chart(px.imshow(D["assets"][mkt].corr(), text_auto=".2f", zmin=-1, zmax=1,
                              color_continuous_scale="RdBu_r", title="Daily return correlations (ZAR)"),
                    use_container_width=True)
    st.caption("Index tickers are proxies: no look-through to constituents, so technology share is a "
               "lower bound. Effective holdings counts synthetic sleeves as holdings.")

with tabs[5]:
    fl = D["flags"].query("portfolio == @pid")
    st.metric("Active exceptions at period end", int(fl["active_at_period_end"].sum()))
    st.dataframe(fl.round(3), hide_index=True, use_container_width=True)
    st.caption("Thresholds are illustrative and to be agreed with the adviser team. "
               "Flags are reporting indicators, not investment decisions.")
    log = D["log"]
    cl = log.get("cleaning", {})
    st.subheader("Data quality")
    st.write(f"Last refresh (UTC): {str(log.get('refreshed_utc', 'unknown'))[:19].replace('T', ' ')} UTC")
    st.write(f"Source: {log.get('source')}")
    st.write(f"Clean window: {cl.get('clean_start')} to {cl.get('clean_end')}; "
             f"{cl.get('cells_forward_filled')} cells forward-filled "
             f"(max gap {cl.get('max_ffill_days')} days)")
    st.write("Source-data corrections")
    st.dataframe(pd.DataFrame(cl.get("known_errors_corrected", [])), hide_index=True,
                 use_container_width=True)
    st.write("Large moves reviewed")
    st.dataframe(pd.DataFrame(cl.get("move_exceptions", [])), hide_index=True,
                 use_container_width=True)
    with st.expander("Missing-data warnings"):
        st.write(log.get("warnings") or "None")