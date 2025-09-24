# Portfolio Tracker App - Paper Trading with IB Integration
# Complete portfolio management with position tracking and P&L analysis

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio

from core.portfolio_manager import PortfolioManager
from core.data_manager import sync_get_real_time_price
from core.backtester import PortfolioBacktester, MovingAverageStrategy, RSIMeanReversionStrategy, BollingerBandsStrategy

# =========================
# Page Configuration
# =========================
st.set_page_config(
    page_title="Portfolio Tracker - Paper Trading",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'portfolio_manager' not in st.session_state:
    st.session_state.portfolio_manager = PortfolioManager(
        initial_cash=100000,
        use_ib=True,
        paper_trading=True
    )

pm = st.session_state.portfolio_manager

# =========================
# Sidebar Controls
# =========================
with st.sidebar:
    st.title("🎯 Portfolio Control")

    st.subheader("📊 Account Summary")

    # Refresh portfolio data
    if st.button("🔄 Refresh Prices"):
        with st.spinner("Updating prices..."):
            try:
                asyncio.run(pm.update_prices())
                st.success("Prices updated!")
            except:
                st.warning("Price update failed - using cached data")
        st.rerun()

    # Portfolio metrics
    summary = pm.get_portfolio_summary()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Value", f"${summary['total_value']:,.2f}")
        st.metric("P&L", f"${summary['total_pnl']:,.2f}",
                 delta=f"{summary['total_pnl_pct']:.1f}%")

    with col2:
        st.metric("Cash", f"${summary['cash_balance']:,.2f}")
        st.metric("Positions", f"{summary['num_positions']}")

    st.divider()

    # Trading Interface
    st.subheader("💼 Place Order")

    with st.form("trade_form"):
        trade_symbol = st.text_input("Symbol", value="AAPL").upper().strip()
        trade_quantity = st.number_input("Quantity", min_value=1, value=100, step=1)
        trade_side = st.selectbox("Side", ["BUY", "SELL"])

        # Get current price for reference
        if trade_symbol:
            try:
                price_data = sync_get_real_time_price(trade_symbol, use_ib=pm.use_ib)
                current_price = price_data['last'] if price_data else 0
                st.info(f"Current Price: ${current_price:.2f}")

                # Order type selection
                order_type = st.selectbox("Order Type", ["Market", "Limit"])

                if order_type == "Limit":
                    limit_price = st.number_input("Limit Price",
                                                value=float(current_price) if current_price > 0 else 100.0,
                                                min_value=0.01, step=0.01)
                else:
                    limit_price = current_price

                # Calculate order value
                order_value = trade_quantity * limit_price
                st.write(f"**Order Value**: ${order_value:,.2f}")

            except:
                current_price = 0
                limit_price = st.number_input("Price", min_value=0.01, value=100.0, step=0.01)

        submitted = st.form_submit_button("🚀 Submit Order")

        if submitted and trade_symbol:
            # Validate order
            quantity_signed = trade_quantity if trade_side == "BUY" else -trade_quantity

            try:
                if order_type == "Market":
                    # Use current market price
                    trade = pm.add_trade(trade_symbol, quantity_signed, current_price)
                else:
                    # Use limit price
                    trade = pm.add_trade(trade_symbol, quantity_signed, limit_price)

                if trade:
                    st.success(f"✅ Order filled: {trade_side} {trade_quantity} {trade_symbol} @ ${trade.price:.2f}")
                    st.rerun()
                else:
                    st.error("❌ Order rejected - check available funds/shares")

            except Exception as e:
                st.error(f"❌ Order failed: {e}")

    st.divider()

    # Quick trades for popular stocks
    st.subheader("⚡ Quick Trades")
    quick_symbols = ["AAPL", "NVDA", "TSLA", "SPY", "QQQ", "MSFT"]

    for symbol in quick_symbols:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(symbol)
        with col2:
            if st.button("Buy", key=f"buy_{symbol}", help=f"Buy 10 shares of {symbol}"):
                try:
                    price_data = sync_get_real_time_price(symbol, use_ib=pm.use_ib)
                    price = price_data['last'] if price_data else 100.0
                    trade = pm.add_trade(symbol, 10, price)
                    if trade:
                        st.success(f"Bought 10 {symbol}")
                        st.rerun()
                except:
                    st.error("Trade failed")
        with col3:
            if st.button("Sell", key=f"sell_{symbol}", help=f"Sell 10 shares of {symbol}"):
                try:
                    price_data = sync_get_real_time_price(symbol, use_ib=pm.use_ib)
                    price = price_data['last'] if price_data else 100.0
                    trade = pm.add_trade(symbol, -10, price)
                    if trade:
                        st.success(f"Sold 10 {symbol}")
                        st.rerun()
                except:
                    st.error("Trade failed")

# =========================
# Main Content
# =========================
st.title("💼 Portfolio Tracker & Paper Trading")
st.caption("Real-time portfolio tracking with Interactive Brokers integration")

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Positions", "📈 Performance", "📋 Trades", "🎯 Analytics", "🔍 Backtesting"])

with tab1:
    st.subheader("Current Positions")

    positions_df = pm.get_positions_df()

    if not positions_df.empty:
        # Format for display
        display_df = positions_df.copy()
        display_df['Market Value'] = display_df['market_value'].apply(lambda x: f"${x:,.2f}")
        display_df['Unrealized P&L'] = display_df['unrealized_pnl'].apply(lambda x: f"${x:,.2f}")
        display_df['P&L %'] = display_df['unrealized_pnl_pct'].apply(lambda x: f"{x:.1f}%")
        display_df['Avg Price'] = display_df['avg_price'].apply(lambda x: f"${x:.2f}")
        display_df['Current Price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}")

        # Select columns for display
        cols_to_show = ['symbol', 'quantity', 'side', 'Avg Price', 'Current Price',
                       'Market Value', 'Unrealized P&L', 'P&L %']

        # Color code P&L
        def color_pnl(val):
            if 'P&L' in val.name:
                if val.str.contains('-').any():
                    return ['background-color: lightcoral' if '-' in str(v) else 'background-color: lightgreen' for v in val]
            return ['' for _ in val]

        styled_df = display_df[cols_to_show].style.apply(color_pnl)
        st.dataframe(styled_df, hide_index=True, use_container_width=True)

        # Position allocation pie chart
        st.subheader("Position Allocation")

        # Calculate allocation by absolute market value
        positions_df['abs_market_value'] = positions_df['market_value'].abs()

        fig_pie = px.pie(positions_df, values='abs_market_value', names='symbol',
                        title="Portfolio Allocation by Position Size")
        st.plotly_chart(fig_pie, use_container_width=True)

    else:
        st.info("No positions found. Use the sidebar to place your first trade!")

with tab2:
    st.subheader("Portfolio Performance")

    # Portfolio summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Portfolio Value", f"${summary['total_value']:,.2f}",
                 delta=f"${summary['total_pnl']:,.2f}")

    with col2:
        st.metric("Cash Balance", f"${summary['cash_balance']:,.2f}")

    with col3:
        positions_value = summary['total_value'] - summary['cash_balance']
        st.metric("Positions Value", f"${positions_value:,.2f}")

    with col4:
        st.metric("Total Return", f"{summary['total_pnl_pct']:.2f}%")

    # Performance chart (simulated daily returns)
    if summary['num_trades'] > 0:
        st.subheader("Portfolio Value Over Time")

        # Create a simple performance simulation
        # In a real system, this would be historical portfolio values
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')

        # Simulate portfolio values with some random walk
        np.random.seed(42)  # For reproducible results
        base_value = pm.initial_cash
        daily_returns = np.random.normal(0.001, 0.02, len(dates))  # 0.1% daily return, 2% volatility
        portfolio_values = [base_value]

        for ret in daily_returns[1:]:
            new_value = portfolio_values[-1] * (1 + ret)
            portfolio_values.append(new_value)

        # Add current value as the last point
        portfolio_values[-1] = summary['total_value']

        perf_df = pd.DataFrame({
            'Date': dates,
            'Portfolio Value': portfolio_values
        })

        fig_perf = px.line(perf_df, x='Date', y='Portfolio Value',
                          title="Portfolio Value Over Time")
        fig_perf.add_hline(y=pm.initial_cash, line_dash="dash",
                          annotation_text="Initial Capital")
        st.plotly_chart(fig_perf, use_container_width=True)

    # Risk metrics
    if not positions_df.empty:
        st.subheader("Risk Analysis")

        col1, col2 = st.columns(2)

        with col1:
            # Position concentration
            max_position = positions_df['market_value'].abs().max()
            concentration = (max_position / summary['total_value']) * 100
            st.metric("Largest Position", f"{concentration:.1f}%")

            # Number of holdings
            st.metric("Number of Holdings", len(positions_df))

        with col2:
            # Long/Short breakdown
            long_value = positions_df[positions_df['quantity'] > 0]['market_value'].sum()
            short_value = positions_df[positions_df['quantity'] < 0]['market_value'].sum()

            st.metric("Long Exposure", f"${long_value:,.2f}")
            st.metric("Short Exposure", f"${abs(short_value):,.2f}")

with tab3:
    st.subheader("Trade History")

    trades_df = pm.get_trades_df()

    if not trades_df.empty:
        # Format trades for display
        display_trades = trades_df.copy()
        display_trades['Trade Value'] = display_trades['trade_value'].apply(lambda x: f"${x:,.2f}")
        display_trades['Price'] = display_trades['price'].apply(lambda x: f"${x:.2f}")
        display_trades['Net Value'] = display_trades['net_value'].apply(lambda x: f"${x:,.2f}")
        display_trades['Trade Date'] = pd.to_datetime(display_trades['trade_date']).dt.strftime('%Y-%m-%d %H:%M')

        # Show recent trades first
        display_trades = display_trades.sort_values('trade_date', ascending=False)

        cols_to_show = ['symbol', 'side', 'quantity', 'Price', 'Trade Value', 'Trade Date']
        st.dataframe(display_trades[cols_to_show], hide_index=True, use_container_width=True)

        # Trading statistics
        st.subheader("Trading Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Trades", len(trades_df))

        with col2:
            buy_trades = len(trades_df[trades_df['side'] == 'BUY'])
            st.metric("Buy Orders", buy_trades)

        with col3:
            sell_trades = len(trades_df[trades_df['side'] == 'SELL'])
            st.metric("Sell Orders", sell_trades)

        with col4:
            total_commissions = trades_df['commission'].sum()
            st.metric("Total Commissions", f"${total_commissions:.2f}")

        # Trading volume by symbol
        symbol_trades = trades_df.groupby('symbol')['trade_value'].sum().reset_index()
        symbol_trades = symbol_trades.sort_values('trade_value', ascending=False)

        if len(symbol_trades) > 0:
            fig_volume = px.bar(symbol_trades, x='symbol', y='trade_value',
                               title="Trading Volume by Symbol")
            st.plotly_chart(fig_volume, use_container_width=True)

    else:
        st.info("No trades yet. Use the sidebar to place your first trade!")

with tab4:
    st.subheader("Portfolio Analytics")

    if not positions_df.empty:
        # Sector allocation (simplified - using symbol prefixes)
        st.write("**Holdings Analysis**")

        # Winners vs Losers
        winners = positions_df[positions_df['unrealized_pnl'] > 0]
        losers = positions_df[positions_df['unrealized_pnl'] < 0]

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Top Performers**")
            if not winners.empty:
                top_winners = winners.nlargest(5, 'unrealized_pnl')[['symbol', 'unrealized_pnl', 'unrealized_pnl_pct']]
                for _, row in top_winners.iterrows():
                    st.success(f"{row['symbol']}: +${row['unrealized_pnl']:.2f} ({row['unrealized_pnl_pct']:.1f}%)")
            else:
                st.info("No winning positions")

        with col2:
            st.write("**Underperformers**")
            if not losers.empty:
                top_losers = losers.nsmallest(5, 'unrealized_pnl')[['symbol', 'unrealized_pnl', 'unrealized_pnl_pct']]
                for _, row in top_losers.iterrows():
                    st.error(f"{row['symbol']}: ${row['unrealized_pnl']:.2f} ({row['unrealized_pnl_pct']:.1f}%)")
            else:
                st.info("No losing positions")

        # P&L distribution
        fig_pnl = px.histogram(positions_df, x='unrealized_pnl_pct', nbins=10,
                              title="P&L Distribution (%)")
        st.plotly_chart(fig_pnl, use_container_width=True)

        # Position size distribution
        positions_df['position_size_pct'] = (positions_df['market_value'].abs() / summary['total_value']) * 100
        fig_size = px.bar(positions_df, x='symbol', y='position_size_pct',
                         title="Position Size as % of Portfolio")
        st.plotly_chart(fig_size, use_container_width=True)

with tab5:
    st.subheader("Strategy Backtesting")
    st.write("Test trading strategies on historical data to evaluate performance")

    # Initialize backtesting session state
    if 'backtester' not in st.session_state:
        st.session_state.backtester = PortfolioBacktester(initial_cash=100000)

    backtester = st.session_state.backtester

    # Backtesting parameters
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Backtest Settings")

        # Symbol selection
        backtest_symbol = st.text_input("Symbol", value="AAPL", help="Stock symbol to backtest")

        # Date range
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("Start Date",
                                     value=datetime.now() - timedelta(days=730),
                                     max_value=datetime.now())
        with col_date2:
            end_date = st.date_input("End Date",
                                   value=datetime.now() - timedelta(days=30),
                                   max_value=datetime.now())

        # Strategy selection
        strategy_options = {
            "Moving Average Crossover": MovingAverageStrategy,
            "RSI Mean Reversion": RSIMeanReversionStrategy,
            "Bollinger Bands": BollingerBandsStrategy
        }

        selected_strategy = st.selectbox("Strategy", list(strategy_options.keys()))
        strategy_class = strategy_options[selected_strategy]

        # Strategy parameters based on selection
        st.subheader("Strategy Parameters")

        strategy_params = {}

        if selected_strategy == "Moving Average Crossover":
            col_ma1, col_ma2 = st.columns(2)
            with col_ma1:
                strategy_params['fast_period'] = st.number_input("Fast MA Period", value=10, min_value=1, max_value=100)
            with col_ma2:
                strategy_params['slow_period'] = st.number_input("Slow MA Period", value=30, min_value=1, max_value=200)

        elif selected_strategy == "RSI Mean Reversion":
            col_rsi1, col_rsi2, col_rsi3 = st.columns(3)
            with col_rsi1:
                strategy_params['rsi_period'] = st.number_input("RSI Period", value=14, min_value=1, max_value=50)
            with col_rsi2:
                strategy_params['rsi_overbought'] = st.number_input("Overbought Level", value=70, min_value=50, max_value=90)
            with col_rsi3:
                strategy_params['rsi_oversold'] = st.number_input("Oversold Level", value=30, min_value=10, max_value=50)

        elif selected_strategy == "Bollinger Bands":
            col_bb1, col_bb2 = st.columns(2)
            with col_bb1:
                strategy_params['period'] = st.number_input("Period", value=20, min_value=1, max_value=100)
            with col_bb2:
                strategy_params['devfactor'] = st.number_input("Std Dev Factor", value=2.0, min_value=0.5, max_value=5.0, step=0.1)

        # Common parameters
        st.subheader("Risk Management")
        col_risk1, col_risk2 = st.columns(2)
        with col_risk1:
            strategy_params['stop_loss'] = st.number_input("Stop Loss %", value=5.0, min_value=0.0, max_value=20.0, step=0.5) / 100
        with col_risk2:
            strategy_params['take_profit'] = st.number_input("Take Profit %", value=15.0, min_value=0.0, max_value=50.0, step=0.5) / 100

    with col2:
        st.subheader("Results")

        # Run backtest button
        if st.button("🚀 Run Backtest", type="primary"):
            with st.spinner(f"Running backtest for {backtest_symbol}..."):
                try:
                    start_str = start_date.strftime('%Y-%m-%d')
                    end_str = end_date.strftime('%Y-%m-%d')

                    # Run the backtest
                    result = backtester.run_backtest(
                        symbol=backtest_symbol,
                        strategy_class=strategy_class,
                        strategy_params=strategy_params,
                        start_date=start_str,
                        end_date=end_str
                    )

                    # Store results in session state
                    st.session_state.backtest_result = result
                    st.success("Backtest completed successfully!")

                except Exception as e:
                    st.error(f"Backtest failed: {str(e)}")

        # Display results if available
        if 'backtest_result' in st.session_state:
            result = st.session_state.backtest_result
            metrics = result.get_performance_metrics()

            st.subheader("Performance Metrics")

            # Key metrics
            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1:
                total_return = metrics.get('Total Return', 0)
                st.metric("Total Return", f"{total_return:.2f}%",
                         delta=f"${metrics.get('Total Return $', 0):.2f}")
            with col_met2:
                sharpe = metrics.get('Sharpe Ratio', 'N/A')
                if sharpe != 'N/A':
                    st.metric("Sharpe Ratio", f"{sharpe:.3f}")
                else:
                    st.metric("Sharpe Ratio", "N/A")
            with col_met3:
                max_dd = metrics.get('Max Drawdown %', 'N/A')
                if max_dd != 'N/A':
                    st.metric("Max Drawdown", f"{max_dd:.2f}%")
                else:
                    st.metric("Max Drawdown", "N/A")

            # Trading metrics
            col_trade1, col_trade2, col_trade3 = st.columns(3)
            with col_trade1:
                st.metric("Total Trades", metrics.get('Total Trades', 0))
            with col_trade2:
                win_rate = metrics.get('Win Rate %', 'N/A')
                if win_rate != 'N/A':
                    st.metric("Win Rate", f"{win_rate:.1f}%")
                else:
                    st.metric("Win Rate", "N/A")
            with col_trade3:
                avg_win = metrics.get('Avg Win $', 'N/A')
                if avg_win != 'N/A':
                    st.metric("Avg Win", f"${avg_win:.2f}")
                else:
                    st.metric("Avg Win", "N/A")

            # Detailed metrics table
            st.subheader("Detailed Results")

            metrics_df = pd.DataFrame([
                {"Metric": "Strategy", "Value": metrics.get('Strategy', '')},
                {"Metric": "Starting Value", "Value": f"${metrics.get('Starting Value', 0):,.2f}"},
                {"Metric": "Ending Value", "Value": f"${metrics.get('Ending Value', 0):,.2f}"},
                {"Metric": "Total Return $", "Value": f"${metrics.get('Total Return $', 0):,.2f}"},
                {"Metric": "Total Trades", "Value": str(metrics.get('Total Trades', 0))},
                {"Metric": "Winning Trades", "Value": str(metrics.get('Winning Trades', 0))},
                {"Metric": "Losing Trades", "Value": str(metrics.get('Losing Trades', 0))},
            ])

            st.dataframe(metrics_df, hide_index=True, use_container_width=True)

            # Plot results
            try:
                st.subheader("Strategy Performance Chart")
                plot_path = backtester.plot_results(backtest_symbol)
                if plot_path:
                    st.image(plot_path, caption=f"{selected_strategy} - {backtest_symbol}")
                else:
                    st.info("Chart generation not available")
            except Exception as e:
                st.warning(f"Could not generate chart: {str(e)}")

    # Strategy comparison section
    st.divider()
    st.subheader("Strategy Comparison")

    if st.button("📊 Compare All Strategies"):
        with st.spinner("Running strategy comparison..."):
            try:
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')

                # Define strategies to compare
                strategies_to_compare = [
                    (MovingAverageStrategy, {'fast_period': 10, 'slow_period': 30}),
                    (RSIMeanReversionStrategy, {'rsi_period': 14, 'rsi_overbought': 70, 'rsi_oversold': 30}),
                    (BollingerBandsStrategy, {'period': 20, 'devfactor': 2.0}),
                ]

                comparison_df = backtester.run_strategy_comparison(
                    symbol=backtest_symbol,
                    strategies=strategies_to_compare,
                    start_date=start_str,
                    end_date=end_str
                )

                st.session_state.comparison_df = comparison_df
                st.success("Strategy comparison completed!")

            except Exception as e:
                st.error(f"Comparison failed: {str(e)}")

    # Display comparison results
    if 'comparison_df' in st.session_state:
        comparison_df = st.session_state.comparison_df

        st.subheader("Strategy Comparison Results")

        # Display comparison table
        display_df = comparison_df.copy()

        # Format numeric columns
        numeric_cols = ['Starting Value', 'Ending Value', 'Total Return', 'Total Return $']
        for col in numeric_cols:
            if col in display_df.columns:
                if col == 'Total Return':
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
                else:
                    display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")

        st.dataframe(display_df, hide_index=True, use_container_width=True)

        # Performance comparison chart
        if len(comparison_df) > 1:
            fig_comp = px.bar(comparison_df, x='Strategy', y='Total Return',
                             title=f"Strategy Performance Comparison - {backtest_symbol}",
                             color='Total Return',
                             color_continuous_scale='RdYlGn')
            fig_comp.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_comp, use_container_width=True)

# =========================
# Footer
# =========================
st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.write(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col2:
    data_source = "Interactive Brokers" if pm.use_ib else "Yahoo Finance"
    st.write(f"**Data Source**: {data_source}")
with col3:
    st.write(f"**Mode**: {'Paper Trading' if pm.paper_trading else 'Live Trading'}")

st.caption("🎮 Paper Trading Environment | Educational purposes only - Not financial advice")

# Auto-refresh option
if st.sidebar.toggle("Auto-refresh (30s)", value=False):
    import time
    time.sleep(30)
    st.rerun()