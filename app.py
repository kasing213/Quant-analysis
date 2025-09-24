# app.py
# Streamlit quant mini — cleaning, stats, CAPM alpha, and a Buy/Hold/Sell signal

import datetime as dt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import plotly.express as px
import streamlit as st
from core.dataproc import load_prices, clean_prices, compute_returns

# =========================
# 1) Config & Defaults
# =========================
st.set_page_config(page_title="Alpha Lab (NVDA)", layout="wide")
DEFAULT_TICKER = "NVDA"
DEFAULT_BENCH  = "SPY"

# =========================
# 2) UI Inputs
# =========================
st.title("NVDA Alpha Lab — Mean → Regression → Signal")
st.caption("Pulls data with yfinance, cleans it, runs stats + CAPM alpha vs benchmark, and outputs a simple Buy/Hold/Sell.")

col0, col1, col2, col3 = st.columns(4)
with col0:
    ticker = st.text_input("Ticker", value=DEFAULT_TICKER).upper().strip()
with col1:
    bench  = st.text_input("Benchmark", value=DEFAULT_BENCH).upper().strip()
with col2:
    start  = st.date_input("Start", dt.date.today() - dt.timedelta(days=365*3))
with col3:
    end    = st.date_input("End", dt.date.today())

lookback = st.slider("Alpha regression lookback (days)", min_value=60, max_value=750, value=252, step=30)

# =========================
# 3) Load & Clean Data
# =========================
asset_px = clean_prices(load_prices(ticker, str(start), str(end)))
bench_px = clean_prices(load_prices(bench,  str(start), str(end)))

# Debug info
st.write("asset_px:", asset_px.shape, list(asset_px.columns))
st.write("bench_px:", bench_px.shape, list(bench_px.columns))

if asset_px.empty:
    st.warning("No price data for the selected asset. Try another date range or ticker.")
    st.stop()

# =========================
# 4) Returns Calculation
# =========================
asset_ret = compute_returns(asset_px)["ret"]
bench_ret = compute_returns(bench_px)["ret"] if not bench_px.empty else pd.Series(dtype=float)

# =========================
# 5) Analysis Functions
# =========================
def summary_stats(ret: pd.Series) -> dict:
    if ret.empty:
        return {"mean": np.nan, "vol": np.nan, "sharpe": np.nan, "cagr": np.nan, "max_dd": np.nan}
    ann = 252
    mu_d = ret.mean()
    sd_d = ret.std(ddof=1)
    sharpe = (mu_d / (sd_d + 1e-12)) * np.sqrt(ann)
    cum = (1 + ret).cumprod()
    n_years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1e-6)
    cagr = cum.iloc[-1] ** (1 / n_years) - 1
    rolling_max = cum.cummax()
    dd = (cum / rolling_max) - 1
    max_dd = dd.min()
    return {
        "mean": mu_d * ann,
        "vol": sd_d * np.sqrt(ann),
        "sharpe": sharpe,
        "cagr": cagr,
        "max_dd": max_dd
    }

def capm_alpha(asset_ret: pd.Series, bench_ret: pd.Series, lookback_days: int = None):
    ra = asset_ret.copy(); ra.name = "ra"
    rm = bench_ret.copy(); rm.name = "rm"
    df = pd.concat([ra, rm], axis=1).dropna()
    if lookback_days is not None and not df.empty:
        cutoff = df.index.max() - pd.Timedelta(days=lookback_days)
        df = df[df.index >= cutoff]
    if df.empty or df["rm"].std() == 0:
        return {"alpha_ann": np.nan, "beta": np.nan, "r2": np.nan,
                "alpha_t": np.nan, "beta_t": np.nan, "alpha_p": np.nan, "beta_p": np.nan}
    X = sm.add_constant(df["rm"].values)
    y = df["ra"].values
    model = sm.OLS(y, X, missing="drop").fit()
    alpha_d, beta = model.params[0], model.params[1]
    r2 = model.rsquared
    t_alpha, t_beta = model.tvalues[0], model.tvalues[1]
    p_alpha, p_beta = model.pvalues[0], model.pvalues[1]
    alpha_ann = alpha_d * 252
    return {"alpha_ann": alpha_ann, "beta": beta, "r2": r2,
            "alpha_t": t_alpha, "beta_t": t_beta, "alpha_p": p_alpha, "beta_p": p_beta}

def sma_signal(price: pd.Series, fast: int = 50, slow: int = 200) -> str:
    if len(price) < max(fast, slow):
        return "HOLD"
    sma_fast = price.rolling(fast).mean()
    sma_slow = price.rolling(slow).mean()
    if sma_fast.iloc[-1] > sma_slow.iloc[-1] * 1.002:
        return "BUY"
    if sma_fast.iloc[-1] < sma_slow.iloc[-1] * 0.998:
        return "SELL"
    return "HOLD"

def blended_decision(alpha_ann: float, last_mkt_ret: float, sma_sig: str) -> str:
    if pd.isna(alpha_ann) or pd.isna(last_mkt_ret):
        return sma_sig
    if sma_sig == "BUY" and alpha_ann > 0:
        return "BUY"
    if sma_sig == "SELL" and alpha_ann < 0:
        return "SELL"
    if alpha_ann > 0 and last_mkt_ret >= 0:
        return "BUY"
    if alpha_ann < 0 and last_mkt_ret < 0:
        return "SELL"
    return "HOLD"

# =========================
# 6) Charts
# =========================
with st.container():
    st.subheader("Price")
    fig_price = px.line(asset_px.reset_index(), x="Date", y="price", title=f"{ticker} Price")
    st.plotly_chart(fig_price, use_container_width=True)

    st.subheader("Cumulative Returns")
    cum_asset = (1 + asset_ret).cumprod(); cum_asset.name = ticker
    cum_df = pd.DataFrame(cum_asset)
    if not bench_ret.empty:
        cum_bench = (1 + bench_ret).cumprod(); cum_bench.name = bench
        cum_df = pd.concat([cum_df, cum_bench], axis=1)
    fig_cum = px.line(cum_df.reset_index(), x="Date", y=cum_df.columns, title="Cumulative Returns (Normalized=1)")
    st.plotly_chart(fig_cum, use_container_width=True)

# =========================
# 7) Stats Tables
# =========================
st.subheader("Summary Stats (Annualized where applicable)")
ast = summary_stats(asset_ret)
bst = summary_stats(bench_ret) if not bench_ret.empty else {k: np.nan for k in ["mean","vol","sharpe","cagr","max_dd"]}
stats_tbl = pd.DataFrame([ast, bst], index=[ticker, bench]).rename(columns={
    "mean":"Mean Return", "vol":"Volatility", "sharpe":"Sharpe (rf≈0)", "cagr":"CAGR", "max_dd":"Max Drawdown"
})
st.dataframe(stats_tbl.style.format({
    "Mean Return": "{:.2%}", "Volatility": "{:.2%}", "Sharpe (rf≈0)": "{:.2f}", "CAGR": "{:.2%}", "Max Drawdown": "{:.2%}",
}), use_container_width=True)

# =========================
# 8) Alpha Regression
# =========================
st.subheader("CAPM-style Regression (Alpha vs Benchmark)")
alpha_res = capm_alpha(asset_ret, bench_ret, lookback_days=lookback)
alpha_tbl = pd.DataFrame([alpha_res]).rename(columns={
    "alpha_ann":"Alpha (annualized)", "beta":"Beta", "r2":"R²",
    "alpha_t":"Alpha t-stat", "beta_t":"Beta t-stat", "alpha_p":"Alpha p-val", "beta_p":"Beta p-val",
})
st.dataframe(alpha_tbl.style.format({
    "Alpha (annualized)":"{:.2%}", "Beta":"{:.2f}", "R²":"{:.3f}", "Alpha t-stat":"{:.2f}",
    "Beta t-stat":"{:.2f}", "Alpha p-val":"{:.3f}", "Beta p-val":"{:.3f}",
}), use_container_width=True)

# =========================
# 9) Signal
# =========================
st.subheader("Signal")
sig_sma = sma_signal(asset_px["price"])
last_mkt_ret = bench_ret.iloc[-1] if not bench_ret.empty else np.nan
sig = blended_decision(alpha_tbl.iloc[0]["Alpha (annualized)"], last_mkt_ret, sig_sma)

colA, colB = st.columns([1,2])
with colA:
    st.metric(label="SMA Signal", value=sig_sma)
    st.metric(label="Final Decision", value=sig)
with colB:
    st.markdown(f"""
**How this decision is made**
- 50/200-day SMA crossover → base signal  
- CAPM alpha sign (annualized) using last **{lookback}** days  
- Latest benchmark daily return for tone check

**Heuristic:**
- BUY if SMA says BUY **and** alpha>0; SELL if SMA says SELL **and** alpha<0  
- Otherwise tilt with alpha sign + market tone; else HOLD
""")

st.caption("Educational only — not financial advice.")
