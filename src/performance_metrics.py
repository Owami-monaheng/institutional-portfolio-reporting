"""Standard performance and risk metrics from a daily return series."""
import numpy as np
import pandas as pd

TD = 252


def total_return(r): return (1 + r).prod() - 1
def cagr(r): return (1 + r).prod() ** (TD / len(r)) - 1
def ann_vol(r): return r.std() * np.sqrt(TD)
def worst_day(r): return r.min()


def max_drawdown(r):
    cum = (1 + r).cumprod()
    return (cum / cum.cummax() - 1).min()


def sharpe(r, rf=0.0):
    v = ann_vol(r)
    return (r.mean() * TD - rf) / v if v > 0 else np.nan   # arithmetic, as in ticker-comparison


def summary(r, rf=0.0) -> dict:
    return {
        "total_return": total_return(r), "cagr": cagr(r), "ann_vol": ann_vol(r),
        "max_drawdown": max_drawdown(r), "sharpe": sharpe(r, rf), "worst_day": worst_day(r),
    }