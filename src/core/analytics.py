import datetime as dt
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.core.dataproc import load_prices, clean_prices, compute_returns
from src.core.analytics import summary_stats, capm_alpha, sma_signal, blended_decision

st.set_page_config(page_title="Alpha Lab (NVDA)", layout="wide")
DEFAULT_TICKER, DEFAULT_BENCH = "NVDA", "SPY"

st.title("NVDA Alpha Lab — Mean → Regression → Signal")
col0, col1, col2, col3 = st.columns(4)
with col0: ticker = st.text_input("Ticker", value=DEFAULT_TICKER).upper().strip()
with col1: bench  = st.text_input("Benchmark", value=DEFAULT_BENCH).upper().strip()
with col2: start  = st.date_input("Start", dt.date.today() - dt.timedelta(days=365*3))
with col3: end    = st.date_input("End", dt.date.today())
lookback = st.slider("Alpha regression lookback (days)", 60, 750, 252, 30)

asset_px = clean_prices(load_prices(ticker, str(start), str(end)))
bench_px = clean_prices(load_prices(bench,  str(start), str(end)))

if asset_px.empty:
    st.warning("No price data. Try a different ticker/range.")
    st.stop()

asset_ret = compute_returns(asset_px)["ret"]
bench_ret = compute_returns(bench_px)["ret"] if not bench_px.empty else pd.Series(dtype=float)

st.subheader("Price")
st.plotly_chart(px.line(asset_px.reset_index(), x="Date", y="price", title=f"{ticker} Price"), use_container_width=True)

st.subheader("Cumulative Returns")
cum_asset = (1 + asset_ret).cumprod(); cum_asset.name = ticker
cum_df = pd.DataFrame(cum_asset)
if not bench_ret.empty:
    cum_bench = (1 + bench_ret).cumprod(); cum_bench.name = bench
    cum_df = pd.concat([cum_df, cum_bench], axis=1)
st.plotly_chart(px.line(cum_df.reset_index(), x="Date", y=cum_df.columns,
                        title="Cumulative Returns (Normalized=1)"), use_container_width=True)

st.subheader("Summary Stats (Annualized where applicable)")
ast = summary_stats(asset_ret)
bst = summary_stats(bench_ret) if not bench_ret.empty else {k: np.nan for k in ["mean","vol","sharpe","cagr","max_dd"]}
st.dataframe(pd.DataFrame([ast, bst], index=[ticker, bench]).rename(columns={
    "mean":"Mean Return","vol":"Volatility","sharpe":"Sharpe (rf≈0)","cagr":"CAGR","max_dd":"Max Drawdown"
}).style.format({"Mean Return":"{:.2%}","Volatility":"{:.2%}","Sharpe (rf≈0)":"{:.2f}","CAGR":"{:.2%}","Max Drawdown":"{:.2%}"}), use_container_width=True)

st.subheader("CAPM-style Regression (Alpha vs Benchmark)")
alpha_tbl = pd.DataFrame([capm_alpha(asset_ret, bench_ret, lookback_days=lookback)]).rename(columns={
    "alpha_ann":"Alpha (annualized)","beta":"Beta","r2":"R²","alpha_t":"Alpha t-stat","beta_t":"Beta t-stat",
    "alpha_p":"Alpha p-val","beta_p":"Beta p-val"
})
st.dataframe(alpha_tbl.style.format({"Alpha (annualized)":"{:.2%}","Beta":"{:.2f}","R²":"{:.3f}","Alpha t-stat":"{:.2f}",
                                     "Beta t-stat":"{:.2f}","Alpha p-val":"{:.3f}","Beta p-val":"{:.3f}"}),
             use_container_width=True)

st.subheader("Signal")
sig_sma = sma_signal(asset_px["price"])
last_mkt_ret = bench_ret.iloc[-1] if not bench_ret.empty else np.nan
sig = blended_decision(alpha_tbl.iloc[0]["Alpha (annualized)"], last_mkt_ret, sig_sma)
c1, c2 = st.columns([1,2])
with c1:
    st.metric("SMA Signal", sig_sma)
    st.metric("Final Decision", sig)
with c2:
    st.markdown(f"""
- 50/200 SMA crossover = base  
- CAPM alpha (last **{lookback}** days)  
- Latest benchmark daily return  
**BUY** if SMA=BUY & alpha>0; **SELL** if SMA=SELL & alpha<0; else tilt; otherwise **HOLD**.
""")
st.caption("Educational only — not financial advice.")
