"""Generate the quarterly reporting pack and one-page executive summary.

Reads the pipeline outputs in data/processed/ and writes reports/quarterly_report.pdf and
reports/executive_summary.pdf. All commentary is rule-based: each sentence is computed from
the data, and none states a cause for a market move.

Usage: python -m src.report_pack
"""
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as esc

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from config.portfolio_config import PORTFOLIOS, SYNTHETIC

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "reports"
HOLD = ROOT / "data" / "synthetic" / "portfolio_holdings.csv"

NAVY = colors.HexColor("#1f3a5f")
GREY = colors.HexColor("#6b7785")
LIGHT = colors.HexColor("#eef1f5")
RF = SYNTHETIC["SA_CASH"]["annual_return"]
RECENT_DAYS = 30


# ---------- formatting helpers ----------
def pct(x, d=1): return f"{x * 100:.{d}f}%"
def pts(x, d=1): return f"{x * 100:+.{d}f} pts"


def join_and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def synth_share(weights):
    return sum(w for t, w in weights.items() if t in SYNTHETIC)


def bench_text():
    return "; ".join(f"Portfolio {p}: " + ", ".join(f"{w * 100:.0f}% {t}" for t, w in cfg["benchmark"].items())
                     for p, cfg in PORTFOLIOS.items())


def bench_text():
    return "; ".join(
        f"Portfolio {p}: " + ", ".join(f"{w * 100:.0f}% {t}" for t, w in cfg["benchmark"].items())
        for p, cfg in PORTFOLIOS.items()
    )


# ---------- data ----------
def load():
    rd = lambda f, **k: pd.read_csv(PROC / f, **k)
    flags = rd("exception_flags.csv")
    flags = flags.astype({"first_breach": object, "last_breach": object}).fillna(
        {"first_breach": "", "last_breach": ""})
    return dict(
        rets=rd("portfolio_returns.csv", index_col=0, parse_dates=True),
        perf=rd("performance_summary.csv").set_index("portfolio"),
        contrib=rd("contribution_analysis.csv"),
        conc=rd("concentration_summary.csv").set_index("portfolio"),
        roll=rd("rolling_metrics.csv", index_col=0, parse_dates=True),
        ccy=rd("currency_exposure_by_portfolio.csv").set_index("portfolio"),
        fx=rd("usdzar_monthly.csv", index_col=0, parse_dates=True).iloc[:, 0],
        flags=flags,
        holdings=pd.read_csv(HOLD),
        log=json.loads((PROC / "refresh_log.json").read_text()),
    )


def fx_stats():
    from src.data_prep import clean_prices
    fx = clean_prices()["USDZAR=X"]
    return fx.iloc[0], fx.iloc[-1], fx.min(), fx.max()


# ---------- rule-based commentary ----------
def findings(D, fx):
    perf, conc, ccy, flags, contrib, rets = (D["perf"], D["conc"], D["ccy"], D["flags"],
                                              D["contrib"], D["rets"])
    fx0, fx1, fxlo, fxhi = fx
    as_of = rets.index.max()
    F = {}

    # Q1 relative performance
    ex = perf["excess_cagr"].sort_values(ascending=False)
    best, worst = ex.index[0], ex.index[-1]
    bench_syn = {p: synth_share(PORTFOLIOS[p]["benchmark"]) for p in perf.index}
    syn_list = [f"Portfolio {p}" for p, s in bench_syn.items() if s >= 0.5]
    short = (f"Portfolio {best} had the strongest relative performance "
             f"({pts(ex[best])} a year against its benchmark)")
    short += (f"; Portfolio {worst} trailed by {abs(ex[worst]) * 100:.1f} pts a year."
              if ex[worst] < 0 else "; all three beat their benchmarks.")
    if syn_list:
        short += (f" Benchmarks for {join_and(syn_list)} are mostly synthetic "
                  f"(assumed bond and cash returns).")
    detail = " ".join(
        f"Portfolio {p}: CAGR {pct(perf.loc[p, 'cagr'])} against {pct(perf.loc[p, 'benchmark_cagr'])} "
        f"for its benchmark ({pts(perf.loc[p, 'excess_cagr'])}), tracking error "
        f"{pct(perf.loc[p, 'tracking_error'])}; {pct(synth_share(PORTFOLIOS[p]['weights']), 0)} of the "
        f"portfolio and {pct(bench_syn[p], 0)} of its benchmark is synthetic."
        for p in perf.index)
    detail += (" Each benchmark mirrors its portfolio's asset-class weights using index proxies, so "
               "differences reflect the chosen holdings against their asset-class index rather than "
               "asset allocation. Synthetic bond and cash sleeves are common to portfolio and benchmark "
               "and largely cancel.")
    F["q1"] = dict(label="Relative performance", short=short, detail=detail)

    # Q2 downside risk
    hv, hd, lv = perf["ann_vol"].idxmax(), perf["max_drawdown"].idxmin(), perf["ann_vol"].idxmin()
    if hv == hd:
        short = (f"Portfolio {hv} carried the most downside risk: highest volatility "
                 f"({pct(perf.loc[hv, 'ann_vol'])}) and deepest drawdown ({pct(perf.loc[hv, 'max_drawdown'])}).")
    else:
        short = (f"Portfolio {hv} had the highest volatility ({pct(perf.loc[hv, 'ann_vol'])}); "
                 f"Portfolio {hd} had the deepest drawdown ({pct(perf.loc[hd, 'max_drawdown'])}).")
    detail = " ".join(
        f"Portfolio {p}: volatility {pct(perf.loc[p, 'ann_vol'])}, maximum drawdown "
        f"{pct(perf.loc[p, 'max_drawdown'])}, worst day {pct(perf.loc[p, 'worst_day'])}, "
        f"Sharpe {perf.loc[p, 'sharpe']:.2f}." for p in perf.index)
    if synth_share(PORTFOLIOS[lv]["weights"]) >= 0.3:
        detail += (f" The lowest-risk portfolio, {lv}, is {pct(synth_share(PORTFOLIOS[lv]['weights']), 0)} "
                   f"synthetic, so its low measured risk partly reflects assumed inputs.")
    detail += f" Sharpe ratios use an assumed {pct(RF, 0)} ZAR cash rate as the risk-free rate."
    F["q2"] = dict(label="Downside risk", short=short, detail=detail)
    def bench_text():
        return "; ".join(f"Portfolio {p}: " + ", ".join(f"{w * 100:.0f}% {t}" for t, w in cfg["benchmark"].items())
                     for p, cfg in PORTFOLIOS.items())

    # Q3 return concentration
    nons = contrib[~contrib["ticker"].str.startswith("SA_")]
    pick = None
    for p in perf.index:
        top2 = nons[nons["portfolio"] == p].nlargest(2, "share_of_total")
        share = top2["share_of_total"].sum()
        if pick is None or share > pick[2]:
            pick = (p, list(top2["ticker"]), share, top2["avg_weight"].sum())
    p3, names, share3, w3 = pick
    note = ("return is more concentrated than the weights suggest." if share3 > 1.15 * w3
            else "broadly in line with those weights.")
    short = (f"In Portfolio {p3}, {names[0]} and {names[1]} supplied {pct(share3, 0)} of total return "
             f"from an average weight of {pct(w3, 0)}; {note}")
    parts = []
    for p in perf.index:
        t1 = nons[nons["portfolio"] == p].nlargest(1, "share_of_total").iloc[0]
        parts.append(f"Portfolio {p}: largest contributor {t1['ticker']} supplied "
                     f"{pct(t1['share_of_total'], 0)} of return (average weight {pct(t1['avg_weight'], 0)}).")
    detail = " ".join(parts)
    tg = conc["tech_share_end"].idxmax()
    if conc.loc[tg, "tech_share_end"] > 0:
        detail += (f" Technology holdings were {pct(conc.loc[tg, 'tech_share_end'], 0)} of Portfolio {tg} at "
                   f"period end. This is a lower bound: index tickers are proxies and are not looked through.")
    detail += " Contribution is the sum of daily weighted returns, so it is additive and differs slightly from compounded return."
    F["q3"] = dict(label="Return concentration", short=short, detail=detail)

    # Q4 currency
    chg = fx1 / fx0 - 1
    word = "strengthened" if chg < 0 else "weakened"
    drag = ccy["currency_drag_compounded"]
    short = (f"The rand {word} {abs(chg) * 100:.1f}% against the dollar over the window "
             f"(USD/ZAR {fx0:.2f} to {fx1:.2f}). Effect on total ZAR return: "
             + "; ".join(f"Portfolio {p} {pts(drag[p])}" for p in perf.index) + ".")
    detail = " ".join(
        f"Portfolio {p}: USD assets averaged {pct(ccy.loc[p, 'usd_asset_weight_avg'], 0)} of the portfolio; "
        f"total return {pct(ccy.loc[p, 'return_zar_actual'])} in ZAR against "
        f"{pct(ccy.loc[p, 'return_if_rand_flat'])} with USD/ZAR held flat." for p in perf.index)
    detail += (f" USD assets include gold futures. USD/ZAR ranged from {fxlo:.2f} to {fxhi:.2f} during the "
               f"window, so these figures are sensitive to the window end date. The compounded comparison "
               f"is the headline; an additive contribution split understates the effect because it ignores compounding.")
    F["q4"] = dict(label="Currency exposure", short=short, detail=detail)

    # Q5 exceptions
    active, recent, ever = [], [], {}
    for _, r in flags.iterrows():
        if r["days_breached"] > 0:
            ever[r["portfolio"]] = ever.get(r["portfolio"], 0) + 1
            if bool(r["active_at_period_end"]):
                active.append(r)
            elif (as_of - pd.Timestamp(r["last_breach"])).days <= RECENT_DAYS:
                recent.append(r)
    desc = lambda r: f"Portfolio {r['portfolio']}: {esc(r['rule'])}"
    parts = []
    if active:
        parts.append("Active at period end: " + "; ".join(desc(r) for r in active) + ".")
    else:
        parts.append("No exception flags were active at the period end.")
    if recent:
        parts.append(f"Breached within the last {RECENT_DAYS} days and now cleared: "
                     + "; ".join(f"{desc(r)} (last breach {r['last_breach']})" for r in recent) + ".")
    if not active and not recent and ever:
        top = max(ever, key=ever.get)
        parts.append(f"Portfolio {top} had the most historical breaches ({ever[top]} rule types).")
    short = " ".join(parts)
    detail = ("Rule types breached at least once during the window: "
              + "; ".join(f"Portfolio {p} {ever.get(p, 0)} of {int((flags['portfolio'] == p).sum())}"
                          for p in perf.index)
              + ". Thresholds are illustrative and to be agreed with the adviser team. Flags are reporting "
                "indicators for adviser review, not investment decisions.")
    F["q5"] = dict(label="Matters for adviser attention", short=short, detail=detail)

    # Q6 automation
    log = D["log"]
    cl = log.get("cleaning", {})
    short = ("One command (python -m src.run_pipeline) refreshes market data, applies documented cleaning "
             "rules, recalculates every metric and regenerates the dashboard and this report.")
    detail = (f"Last data refresh: {str(log.get('refreshed_utc', 'unknown'))[:19].replace('T', ' ')} UTC. The run applied "
              f"{len(cl.get('known_errors_corrected', []))} documented source-data corrections and logged "
              f"{len(cl.get('move_exceptions', []))} large moves for review. Every refresh records the data "
              f"source, coverage, missing-data warnings and cleaning actions, so each figure can be traced.")
    F["q6"] = dict(label="Automation", short=short, detail=detail)
    return F


# ---------- charts ----------
def fig_image(fig, width_mm=180):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    iw, ih = ImageReader(buf).getSize()
    buf.seek(0)
    w = width_mm * mm
    return Image(buf, width=w, height=w * ih / iw)


def style_ax(ax):
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25)


def fig_cumulative(D):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3), sharey=True)
    for ax, p in zip(axes, PORTFOLIOS):
        cum = (1 + D["rets"][[f"Portfolio {p}", f"Benchmark {p}"]]).cumprod() - 1
        ax.plot(cum.index, cum[f"Portfolio {p}"], color="#1f3a5f", lw=1.6, label="Portfolio")
        ax.plot(cum.index, cum[f"Benchmark {p}"], color="#8a94a0", lw=1.3, ls="--", label="Benchmark")
        ax.set_title(f"Portfolio {p}", fontsize=9)
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        style_ax(ax)
    axes[0].legend(fontsize=7, frameon=False)
    return fig_image(fig)


def fig_contribution(D):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
    for ax, p in zip(axes, PORTFOLIOS):
        c = D["contrib"][D["contrib"]["portfolio"] == p].sort_values("contribution")
        cols = ["#b8c0cb" if t.startswith("SA_") else "#1f3a5f" for t in c["ticker"]]
        ax.barh(c["ticker"], c["contribution"], color=cols)
        ax.set_title(f"Portfolio {p}", fontsize=9)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        style_ax(ax)
    fig.tight_layout()
    return fig_image(fig)


def fig_drawdown(D):
    fig, ax = plt.subplots(figsize=(11, 2.8))
    for p, c in zip(PORTFOLIOS, ["#1f3a5f", "#c0792a", "#3d8f6b"]):
        ax.plot(D["roll"].index, D["roll"][f"{p}_drawdown"], color=c, lw=1.3, label=f"Portfolio {p}")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_title("Drawdown from peak", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    style_ax(ax)
    return fig_image(fig)


def fig_fx(D):
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.plot(D["fx"].index, D["fx"].values, color="#1f3a5f", lw=1.5)
    ax.set_title("USD/ZAR, month-end (higher = weaker rand)", fontsize=9)
    style_ax(ax)
    return fig_image(fig)


# ---------- pdf building blocks ----------
def make_styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontSize=18, textColor=NAVY, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=GREY, leading=10.5, spaceAfter=6),
        "h1": ParagraphStyle("h", parent=ss["Heading2"], fontSize=13, textColor=NAVY, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12, spaceAfter=4),
        "small": ParagraphStyle("sm", parent=ss["Normal"], fontSize=7.5, leading=9.5, textColor=GREY, spaceAfter=4),
        "cell": ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9),
        "bullet": ParagraphStyle("bl", parent=ss["Normal"], fontSize=9, leading=12, leftIndent=11,
                                 bulletIndent=0, spaceAfter=3),
    }


def tbl(data, widths_mm, right_from=1, font=8):
    t = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), font),
        ("ALIGN", (right_from, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d1da")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    style += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY)
    canvas.drawString(15 * mm, 8 * mm, "SIMULATION: synthetic holdings and assumed bond/cash returns. "
                                       "Reporting only, not investment advice.")
    canvas.drawRightString(A4[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def trailing_rows(rets):
    rows = [["Period", "Portfolio", "Portfolio return", "Benchmark return", "Difference (pts)"]]
    for label, n in [("3 months (63 days)", 63), ("6 months (126 days)", 126),
                     ("12 months (252 days)", 252), ("Full window", None)]:
        for p in PORTFOLIOS:
            a, b = rets[f"Portfolio {p}"], rets[f"Benchmark {p}"]
            if n:
                a, b = a.iloc[-n:], b.iloc[-n:]
            pr, br = (1 + a).prod() - 1, (1 + b).prod() - 1
            rows.append([label, p, pct(pr), pct(br), f"{(pr - br) * 100:+.1f}"])
    return rows


def meta_line(D, now):
    r = D["rets"]
    return (f"Meridian Private Wealth and Capital (fictional case study). All figures in ZAR. "
            f"Data as of {r.index.max():%d %b %Y}; window {r.index.min():%d %b %Y} to "
            f"{r.index.max():%d %b %Y} ({len(r)} trading days). Market data refreshed "
            f"{D['log'].get('refreshed_utc', 'unknown')[:19]} UTC. Report generated {now:%d %b %Y %H:%M} UTC.")


# ---------- quarterly pack ----------
def build_pack(D, F, now):
    st = make_styles()
    perf, conc, ccy, log = D["perf"], D["conc"], D["ccy"], D["log"]
    cl = log.get("cleaning", {})
    doc = SimpleDocTemplate(str(OUT / "quarterly_report.pdf"), pagesize=A4, leftMargin=15 * mm,
                            rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                            title="Quarterly Portfolio Performance and Risk Report")
    S = [Paragraph("Quarterly Portfolio Performance &amp; Risk Report", st["title"]),
         Paragraph(esc(meta_line(D, now)), st["sub"]),
         Paragraph("Key findings", st["h1"])]
    for k in ["q1", "q2", "q3", "q4", "q5", "q6"]:
        S.append(Paragraph(f"<b>{F[k]['label']}.</b> {F[k]['short']}", st["bullet"], bulletText="-"))

    # 1 Performance
    S.append(Paragraph("1. Performance against benchmark", st["h1"]))
    rows = [["Portfolio", "Mandate", "Total return", "CAGR", "Benchmark CAGR", "Diff (pts/yr)", "Tracking error"]]
    for p in perf.index:
        r = perf.loc[p]
        rows.append([p, r["mandate"], pct(r["total_return"]), pct(r["cagr"]), pct(r["benchmark_cagr"]),
                     f"{r['excess_cagr'] * 100:+.1f}", pct(r["tracking_error"])])
    S += [tbl(rows, [18, 42, 24, 20, 28, 24, 24], right_from=2), Spacer(1, 5),
          Paragraph(F["q1"]["detail"], st["body"]),
          KeepTogether([fig_cumulative(D), Paragraph("Cumulative return in ZAR, portfolio against benchmark.", st["small"])]),
          KeepTogether([tbl(trailing_rows(D["rets"]), [40, 20, 38, 38, 38], right_from=1),
                        Paragraph("Trailing periods are the last 63, 126 and 252 trading days to the data date.", st["small"])])]

    # 2 Contribution and concentration
    S.append(Paragraph("2. Contribution and concentration", st["h1"]))
    rows = [["Portfolio", "Holding", "Average weight", "Contribution", "Share of total"]]
    for p in perf.index:
        for _, r in D["contrib"][D["contrib"]["portfolio"] == p].nlargest(3, "contribution").iterrows():
            name = r["ticker"] + (" (synthetic)" if r["ticker"].startswith("SA_") else "")
            rows.append([p, name, pct(r["avg_weight"]), pct(r["contribution"]), pct(r["share_of_total"], 0)])
    S += [Paragraph(F["q3"]["detail"], st["body"]),
          KeepTogether([fig_contribution(D), Paragraph(
              "Contribution to return by holding (sum of daily weighted returns). Grey bars are synthetic sleeves.",
              st["small"])]),
          tbl(rows, [22, 50, 32, 32, 32], right_from=2),
          Paragraph("Top three contributors per portfolio.", st["small"])]
    rows = [["Portfolio", "Largest holding", "Weight", "Effective holdings", "Technology", "International", "Avg pair corr."]]
    for p in perf.index:
        c = conc.loc[p]
        rows.append([p, c["largest_holding_end"], pct(c["largest_weight_end"], 0), f"{1 / c['hhi_end']:.1f}",
                     pct(c["tech_share_end"], 0), pct(c["intl_share_end"], 0), f"{c['avg_pairwise_corr']:.2f}"])
    S += [Spacer(1, 4), tbl(rows, [20, 34, 20, 32, 24, 26, 26], right_from=2),
          Paragraph("Position at period end. Effective holdings = 1 / Herfindahl index and counts synthetic sleeves "
                    "as holdings. Average pairwise correlation covers market (non-synthetic) holdings only.", st["small"])]

    # 3 Risk
    S.append(Paragraph("3. Risk and volatility", st["h1"]))
    rows = [["Portfolio", "Volatility", "Max drawdown", "Sharpe", "Worst day"]]
    for p in perf.index:
        r = perf.loc[p]
        rows.append([p, pct(r["ann_vol"]), pct(r["max_drawdown"]), f"{r['sharpe']:.2f}", pct(r["worst_day"])])
    S += [tbl(rows, [26, 34, 38, 28, 34]), Spacer(1, 5), Paragraph(F["q2"]["detail"], st["body"]),
          KeepTogether([fig_drawdown(D), Paragraph("Drawdown from running peak, ZAR.", st["small"])])]

    # 4 Currency
    S.append(Paragraph("4. Currency exposure", st["h1"]))
    rows = [["Portfolio", "USD assets (avg)", "Return, rand flat", "Actual ZAR return", "Drag (pts)", "CAGR flat", "CAGR actual"]]
    for p in perf.index:
        c = ccy.loc[p]
        rows.append([p, pct(c["usd_asset_weight_avg"], 0), pct(c["return_if_rand_flat"]), pct(c["return_zar_actual"]),
                     f"{c['currency_drag_compounded'] * 100:+.1f}", pct(c["cagr_if_rand_flat"]), pct(c["cagr_zar_actual"])])
    S += [tbl(rows, [20, 28, 28, 30, 22, 24, 26]), Spacer(1, 5), Paragraph(F["q4"]["detail"], st["body"]),
          KeepTogether([fig_fx(D), Paragraph("Month-end USD/ZAR.", st["small"])])]

    # 5 Exceptions
    S.append(Paragraph("5. Exceptions for adviser attention", st["h1"]))
    S.append(Paragraph(F["q5"]["short"] + " " + F["q5"]["detail"], st["body"]))
    rows = [["Portfolio", "Rule", "Days", "First", "Last", "Worst", "Active"]]
    for _, r in D["flags"].iterrows():
        worst = "" if pd.isna(r["worst_value"]) else f"{r['worst_value']:.3f}"
        rows.append([r["portfolio"], Paragraph(esc(r["rule"]), st["cell"]), int(r["days_breached"]),
                     r["first_breach"], r["last_breach"], worst, "Yes" if bool(r["active_at_period_end"]) else "No"])
    S.append(tbl(rows, [16, 66, 14, 24, 24, 18, 14], right_from=2, font=7.5))

    # 6 Data quality, method, limitations
    S.append(Paragraph("6. Data quality, method and limitations", st["h1"]))
    S.append(Paragraph(f"Source: {esc(str(log.get('source')))}. Clean window {cl.get('clean_start')} to "
                       f"{cl.get('clean_end')}; {cl.get('cells_forward_filled')} cells forward-filled "
                       f"(maximum gap {cl.get('max_ffill_days')} days).", st["body"]))
    if cl.get("known_errors_corrected"):
        rows = [["Ticker", "Date", "Confirmed source-data error", "Treatment"]]
        for e in cl["known_errors_corrected"]:
            rows.append([e["ticker"], e["date"], Paragraph(esc(e["issue"]), st["cell"]),
                         Paragraph(esc(e["treatment"]), st["cell"])])
        S += [tbl(rows, [22, 22, 80, 40], right_from=9, font=7.5), Spacer(1, 4)]
    if cl.get("move_exceptions"):
        rows = [["Ticker", "Date", "Move", "Review status"]]
        for e in cl["move_exceptions"]:
            rows.append([e["ticker"], e["date"], pct(e["move"]), Paragraph(esc(e.get("status", "")), st["cell"])])
        S += [tbl(rows, [22, 22, 20, 100], right_from=2, font=7.5), Spacer(1, 4)]
    method = [
        "Prices: adjusted close from Yahoo Finance. Index tickers are price indices (no dividends); single stocks are total return.",
        "Rand conversion compounds the dollar return and the USD/ZAR change. JSE prices are converted from cents to rand.",
        "Portfolios are rebalanced quarterly to target weights, with weights drifting in between.",
        f"Benchmarks mirror each portfolio's asset-class weights using index proxies. {bench_text()}. "
        "STX40.JO (Satrix 40 ETF) is the JSE Top 40 proxy.",
                f"Benchmarks mirror each portfolio's asset-class weights using index proxies. {bench_text()}. "
        "STX40.JO (Satrix 40 ETF) is the JSE Top 40 proxy.",
        "Volatility, Sharpe and tracking error use 252 trading days. Sharpe uses an arithmetic mean return.",
        f"Synthetic sleeves: SA_BONDS {pct(SYNTHETIC['SA_BONDS']['annual_return'], 0)} return with "
        f"{pct(SYNTHETIC['SA_BONDS']['annual_vol'], 0)} volatility; SA_CASH {pct(SYNTHETIC['SA_CASH']['annual_return'], 0)}. "
        "These are assumptions, not observations.",
        "Exception thresholds are illustrative and to be agreed with the adviser team.",
        "Gold is a futures series (contract-roll effects). Index tickers are not looked through to constituents.",
    ]
    for m in method:
        S.append(Paragraph(esc(m), st["bullet"], bulletText="-"))

    # 7 Automation
    S.append(Paragraph("7. How this report was produced", st["h1"]))
    S.append(Paragraph(F["q6"]["short"] + " " + F["q6"]["detail"], st["body"]))
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    return doc.page


# ---------- one-page executive summary ----------
def build_exec(D, F, now):
    st = make_styles()
    for k in ("body", "bullet"):
        st[k].fontSize, st[k].leading = 8.6, 11
    perf, ccy, log = D["perf"], D["ccy"], D["log"]
    cl = log.get("cleaning", {})
    doc = SimpleDocTemplate(str(OUT / "executive_summary.pdf"), pagesize=A4, leftMargin=15 * mm,
                            rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                            title="Executive Management Summary")
    S = [Paragraph("Executive Management Summary", st["title"]),
         Paragraph(esc(meta_line(D, now)), st["sub"]),
         Paragraph("Key findings", st["h1"])]
    for k in ["q1", "q2", "q3", "q4"]:
        S.append(Paragraph(f"<b>{F[k]['label']}.</b> {F[k]['short']}", st["bullet"], bulletText="-"))

    rows = [["Portfolio", "Total return", "CAGR", "vs bench (pts/yr)", "Volatility", "Max drawdown", "Sharpe", "Currency (pts)"]]
    for p in perf.index:
        r = perf.loc[p]
        rows.append([f"{p} ({r['mandate']})", pct(r["total_return"]), pct(r["cagr"]), f"{r['excess_cagr'] * 100:+.1f}",
                     pct(r["ann_vol"]), pct(r["max_drawdown"]), f"{r['sharpe']:.2f}",
                     f"{ccy.loc[p, 'currency_drag_compounded'] * 100:+.1f}"])
    S += [Spacer(1, 4), tbl(rows, [40, 20, 15, 24, 18, 22, 14, 22], right_from=1, font=7.5),
          Paragraph("Matters requiring attention", st["h1"]),
          Paragraph(F["q5"]["short"], st["body"]),
          Paragraph("Reporting limitations", st["h1"])]
    limits = [
        f"Holdings and weights are synthetic. Bond and cash returns are assumed ({pct(SYNTHETIC['SA_BONDS']['annual_return'], 0)} "
        f"and {pct(SYNTHETIC['SA_CASH']['annual_return'], 0)} a year), so results for portfolios with large synthetic sleeves "
        f"reflect those assumptions.",
        "Exception thresholds are illustrative and need agreeing with advisers. Flags are indicators for review, not investment decisions.",
        "Index tickers are proxies and are not looked through, so technology exposure is a lower bound.",
        f"{len(cl.get('known_errors_corrected', []))} confirmed source-data errors were corrected and "
        f"{len(cl.get('move_exceptions', []))} large moves were reviewed (detail in the quarterly report).",
    ]
    for t in limits:
        S.append(Paragraph(esc(t), st["bullet"], bulletText="-"))
    S.append(Paragraph(f"<b>Automation.</b> {F['q6']['short']}", st["bullet"], bulletText="-"))
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    return doc.page


def main():
    OUT.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    D = load()
    F = findings(D, fx_stats())
    n1 = build_pack(D, F, now)
    n2 = build_exec(D, F, now)
    print(f"reports/quarterly_report.pdf: {n1} pages")
    print(f"reports/executive_summary.pdf: {n2} page(s)")
    if n2 > 1:
        print("WARNING: executive summary runs over one page; shorten the findings text.")


if __name__ == "__main__":
    main()