# Enhanced Streamlit App with Interactive Brokers Integration
# Multi-stock analysis, portfolio tracking, and paper trading capabilities

import datetime as dt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
import asyncio
from typing import Dict, List

from core.data_manager import sync_get_price_data, sync_get_multiple_stocks, sync_get_real_time_price
from core.dataproc import clean_prices, compute_returns

# =========================
# 1) Config & Setup
# =========================
st.set_page_config(
    page_title="Quant Trading Lab - IB Enhanced",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['NVDA', 'AAPL', 'TSLA', 'SPY', 'QQQ']
if 'use_ib' not in st.session_state:
    st.session_state.use_ib = True
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = {}

# =========================
# 2) Sidebar Configuration
# =========================
with st.sidebar:
    st.title("🚀 Quant Lab Settings")

    # Data source selection
    st.subheader("📡 Data Source")
    use_ib = st.toggle("Use Interactive Brokers", value=st.session_state.use_ib,
                      help="Toggle between IB (real-time) and Yahoo Finance (free)")
    st.session_state.use_ib = use_ib

    if use_ib:
        st.success("🔗 IB Mode: Real-time data + Trading")
        ib_status = st.empty()
    else:
        st.info("📈 Yahoo Finance Mode: Free data only")

    st.divider()

    # Watchlist management
    st.subheader("📊 Stock Watchlist")

    # Add new stock
    new_stock = st.text_input("Add Stock", placeholder="e.g., MSFT").upper().strip()
    if st.button("➕ Add") and new_stock and new_stock not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_stock)
        st.rerun()

    # Show current watchlist
    watchlist_df = pd.DataFrame({'Symbol': st.session_state.watchlist})
    st.dataframe(watchlist_df, hide_index=True, use_container_width=True)

    # Remove stock
    if st.session_state.watchlist:
        remove_stock = st.selectbox("Remove Stock", [""] + st.session_state.watchlist)
        if st.button("❌ Remove") and remove_stock:
            st.session_state.watchlist.remove(remove_stock)
            st.rerun()

    st.divider()

    # Analysis settings
    st.subheader("⚙️ Analysis Settings")
    period = st.selectbox("Time Period", ['1mo', '3mo', '6mo', '1y', '2y'], index=3)
    lookback = st.slider("Alpha Lookback (days)", 60, 750, 252, 30)
    benchmark = st.selectbox("Benchmark", ['SPY', 'QQQ', 'IWM', '^GSPC'], index=0)

# =========================
# 3) Main Content
# =========================
st.title("🎯 Quantitative Trading Laboratory")
st.caption("Professional-grade analysis with Interactive Brokers integration")

# Quick status check for IB
if use_ib:
    with st.spinner("Testing IB connection..."):
        try:
            test_data = sync_get_real_time_price('SPY', use_ib=True)
            if test_data:
                st.success(f"✅ IB Connected - SPY: ${test_data['last']:.2f}")
            else:
                st.warning("⚠️ IB not connected - using Yahoo Finance fallback")
                use_ib = False
        except:
            st.error("❌ IB connection failed - using Yahoo Finance")
            use_ib = False

# =========================
# 4) Multi-Stock Analysis
# =========================
st.header("📈 Multi-Stock Analysis")

if st.session_state.watchlist:
    with st.spinner(f"Loading data for {len(st.session_state.watchlist)} stocks..."):
        # Get data for all stocks
        stock_data = sync_get_multiple_stocks(st.session_state.watchlist, period=period, use_ib=use_ib)
        bench_data = sync_get_price_data(benchmark, period=period, use_ib=use_ib)

    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Performance", "🎯 Signals", "💼 Portfolio"])

    with tab1:
        st.subheader("Stock Overview & Real-time Prices")

        overview_data = []
        for symbol in st.session_state.watchlist:
            if symbol in stock_data and not stock_data[symbol].empty:
                df = stock_data[symbol]
                returns = compute_returns(df)['ret']

                # Get real-time price if available
                rt_price = None
                if use_ib:
                    rt_data = sync_get_real_time_price(symbol, use_ib=True)
                    rt_price = rt_data['last'] if rt_data else None

                current_price = rt_price or df['price'].iloc[-1]
                daily_return = returns.iloc[-1] if len(returns) > 0 else 0

                overview_data.append({
                    'Symbol': symbol,
                    'Price': f"${current_price:.2f}",
                    'Daily Return': f"{daily_return:.2%}",
                    'Period Return': f"{(df['price'].iloc[-1] / df['price'].iloc[0] - 1):.2%}",
                    'Volatility': f"{returns.std() * np.sqrt(252):.1%}",
                    'Data Source': "IB Real-time" if rt_price else "Historical"
                })

        if overview_data:
            overview_df = pd.DataFrame(overview_data)
            st.dataframe(overview_df, hide_index=True, use_container_width=True)

    with tab2:
        st.subheader("Cumulative Performance Comparison")

        # Create performance chart
        cum_returns = pd.DataFrame()

        for symbol in st.session_state.watchlist:
            if symbol in stock_data and not stock_data[symbol].empty:
                returns = compute_returns(stock_data[symbol])['ret']
                cum_ret = (1 + returns).cumprod()
                cum_returns[symbol] = cum_ret

        # Add benchmark
        if not bench_data.empty:
            bench_returns = compute_returns(bench_data)['ret']
            cum_returns[f"{benchmark} (Benchmark)"] = (1 + bench_returns).cumprod()

        if not cum_returns.empty:
            fig = px.line(cum_returns.reset_index(), x='Date', y=cum_returns.columns,
                         title="Cumulative Returns Comparison")
            fig.update_layout(yaxis_title="Cumulative Return", legend_title="Assets")
            st.plotly_chart(fig, use_container_width=True)

            # Performance metrics table
            st.subheader("Performance Metrics")
            perf_metrics = []

            for symbol in st.session_state.watchlist:
                if symbol in stock_data and not stock_data[symbol].empty:
                    returns = compute_returns(stock_data[symbol])['ret']

                    if len(returns) > 0:
                        ann_return = returns.mean() * 252
                        ann_vol = returns.std() * np.sqrt(252)
                        sharpe = ann_return / ann_vol if ann_vol > 0 else 0

                        cum_ret = (1 + returns).cumprod()
                        max_dd = ((cum_ret / cum_ret.cummax()) - 1).min()

                        perf_metrics.append({
                            'Symbol': symbol,
                            'Ann. Return': f"{ann_return:.1%}",
                            'Ann. Volatility': f"{ann_vol:.1%}",
                            'Sharpe Ratio': f"{sharpe:.2f}",
                            'Max Drawdown': f"{max_dd:.1%}"
                        })

            if perf_metrics:
                perf_df = pd.DataFrame(perf_metrics)
                st.dataframe(perf_df, hide_index=True, use_container_width=True)

    with tab3:
        st.subheader("Trading Signals & Alpha Analysis")

        signals_data = []

        for symbol in st.session_state.watchlist:
            if symbol in stock_data and not stock_data[symbol].empty:
                asset_data = stock_data[symbol]
                asset_ret = compute_returns(asset_data)['ret']
                bench_ret = compute_returns(bench_data)['ret'] if not bench_data.empty else pd.Series()

                # CAPM Alpha calculation
                def capm_alpha(asset_ret, bench_ret, lookback_days=None):
                    ra = asset_ret.copy()
                    rm = bench_ret.copy()
                    df = pd.concat([ra, rm], axis=1).dropna()
                    df.columns = ['ra', 'rm']

                    if lookback_days and not df.empty:
                        cutoff = df.index.max() - pd.Timedelta(days=lookback_days)
                        df = df[df.index >= cutoff]

                    if df.empty or df['rm'].std() == 0:
                        return {'alpha_ann': np.nan, 'beta': np.nan, 'r2': np.nan}

                    X = sm.add_constant(df['rm'].values)
                    y = df['ra'].values
                    model = sm.OLS(y, X, missing="drop").fit()

                    alpha_d, beta = model.params[0], model.params[1]
                    alpha_ann = alpha_d * 252
                    r2 = model.rsquared

                    return {'alpha_ann': alpha_ann, 'beta': beta, 'r2': r2}

                # SMA Signal
                def sma_signal(prices, fast=50, slow=200):
                    if len(prices) < max(fast, slow):
                        return "HOLD"
                    sma_fast = prices.rolling(fast).mean().iloc[-1]
                    sma_slow = prices.rolling(slow).mean().iloc[-1]

                    if sma_fast > sma_slow * 1.002:
                        return "BUY"
                    elif sma_fast < sma_slow * 0.998:
                        return "SELL"
                    return "HOLD"

                alpha_res = capm_alpha(asset_ret, bench_ret, lookback) if not bench_ret.empty else {'alpha_ann': np.nan, 'beta': np.nan, 'r2': np.nan}
                signal = sma_signal(asset_data['price'])

                signals_data.append({
                    'Symbol': symbol,
                    'Signal': signal,
                    'Alpha (Ann.)': f"{alpha_res['alpha_ann']:.1%}" if not pd.isna(alpha_res['alpha_ann']) else "N/A",
                    'Beta': f"{alpha_res['beta']:.2f}" if not pd.isna(alpha_res['beta']) else "N/A",
                    'R²': f"{alpha_res['r2']:.3f}" if not pd.isna(alpha_res['r2']) else "N/A"
                })

        if signals_data:
            signals_df = pd.DataFrame(signals_data)

            # Color code signals
            def color_signals(val):
                if val == 'BUY':
                    return 'background-color: lightgreen'
                elif val == 'SELL':
                    return 'background-color: lightcoral'
                else:
                    return 'background-color: lightyellow'

            styled_df = signals_df.style.applymap(color_signals, subset=['Signal'])
            st.dataframe(styled_df, hide_index=True, use_container_width=True)

    with tab4:
        st.subheader("💼 Portfolio Simulation")

        st.info("🚧 Coming soon: Paper trading integration with IB")

        # Equal weight portfolio simulation
        if len(st.session_state.watchlist) > 1:
            st.write("**Equal Weight Portfolio Simulation**")

            equal_weight_returns = pd.Series(dtype=float)
            weights = 1.0 / len(st.session_state.watchlist)

            for symbol in st.session_state.watchlist:
                if symbol in stock_data and not stock_data[symbol].empty:
                    returns = compute_returns(stock_data[symbol])['ret']
                    if equal_weight_returns.empty:
                        equal_weight_returns = returns * weights
                    else:
                        equal_weight_returns = equal_weight_returns.add(returns * weights, fill_value=0)

            if not equal_weight_returns.empty:
                portfolio_value = (1 + equal_weight_returns).cumprod() * 100000  # $100k starting value

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=portfolio_value.index, y=portfolio_value,
                                       name="Equal Weight Portfolio", line=dict(color='blue', width=3)))

                fig.update_layout(title="Portfolio Value Over Time ($100,000 starting capital)",
                                yaxis_title="Portfolio Value ($)", xaxis_title="Date")
                st.plotly_chart(fig, use_container_width=True)

                # Portfolio metrics
                portfolio_return = equal_weight_returns.mean() * 252
                portfolio_vol = equal_weight_returns.std() * np.sqrt(252)
                portfolio_sharpe = portfolio_return / portfolio_vol if portfolio_vol > 0 else 0

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Portfolio Return", f"{portfolio_return:.1%}")
                col2.metric("Portfolio Volatility", f"{portfolio_vol:.1%}")
                col3.metric("Sharpe Ratio", f"{portfolio_sharpe:.2f}")
                col4.metric("Current Value", f"${portfolio_value.iloc[-1]:,.0f}")

else:
    st.warning("Please add some stocks to your watchlist using the sidebar.")

# =========================
# 5) Footer
# =========================
st.divider()
st.caption("🤖 Enhanced with Interactive Brokers API | Educational purposes only - Not financial advice")

# Auto-refresh option
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()