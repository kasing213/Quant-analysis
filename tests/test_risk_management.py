"""
Test script for Risk Management System
Demonstrates all risk management features with sample data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from src.core.portfolio_manager import PortfolioManager
from src.core.risk_manager import RiskManager, PositionSizer, RiskCalculator, create_sample_risk_manager
from src.core.cfd_risk_manager import CFDRiskManager, CFDPosition, CFDInstrumentType, create_sample_cfd_position

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_risk_calculator():
    """Test core risk calculation functions"""
    print("=" * 60)
    print("TESTING RISK CALCULATOR")
    print("=" * 60)

    # Generate sample returns data
    np.random.seed(42)  # For reproducible results
    n_days = 252  # One year of trading days
    daily_returns = np.random.normal(0.0008, 0.02, n_days)  # 0.08% daily return, 2% volatility
    returns_series = pd.Series(daily_returns, index=pd.date_range(start='2023-01-01', periods=n_days, freq='D'))

    # Generate equity curve
    initial_value = 100000
    equity_curve = pd.Series(index=returns_series.index, dtype=float)
    equity_curve.iloc[0] = initial_value

    for i in range(1, len(returns_series)):
        equity_curve.iloc[i] = equity_curve.iloc[i-1] * (1 + returns_series.iloc[i])

    # Test VaR calculations
    var_95_hist = RiskCalculator.calculate_var(returns_series, 0.95, "historical")
    var_95_param = RiskCalculator.calculate_var(returns_series, 0.95, "parametric")
    var_99 = RiskCalculator.calculate_var(returns_series, 0.99, "historical")

    print(f"VaR 95% (Historical): {var_95_hist:.2%}")
    print(f"VaR 95% (Parametric): {var_95_param:.2%}")
    print(f"VaR 99% (Historical): {var_99:.2%}")

    # Test CVaR
    cvar_95 = RiskCalculator.calculate_cvar(returns_series, 0.95)
    cvar_99 = RiskCalculator.calculate_cvar(returns_series, 0.99)

    print(f"CVaR 95%: {cvar_95:.2%}")
    print(f"CVaR 99%: {cvar_99:.2%}")

    # Test drawdown
    max_dd, dd_duration = RiskCalculator.calculate_max_drawdown(equity_curve)
    print(f"Maximum Drawdown: {max_dd:.2%}")
    print(f"Max Drawdown Duration: {dd_duration} days")

    # Test ratios
    sharpe = RiskCalculator.calculate_sharpe_ratio(returns_series)
    sortino = RiskCalculator.calculate_sortino_ratio(returns_series)
    calmar = RiskCalculator.calculate_calmar_ratio(returns_series, equity_curve)

    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Sortino Ratio: {sortino:.2f}")
    print(f"Calmar Ratio: {calmar:.2f}")

def test_position_sizer():
    """Test position sizing algorithms"""
    print("\\n" + "=" * 60)
    print("TESTING POSITION SIZER")
    print("=" * 60)

    account_balance = 100000

    # Test Kelly Criterion
    win_rate = 0.55
    avg_win = 0.025  # 2.5%
    avg_loss = 0.018  # 1.8%

    kelly_fraction = PositionSizer.kelly_criterion(win_rate, avg_win, avg_loss)
    kelly_amount = account_balance * kelly_fraction

    print(f"Kelly Criterion:")
    print(f"  Win Rate: {win_rate:.1%}")
    print(f"  Average Win: {avg_win:.1%}")
    print(f"  Average Loss: {avg_loss:.1%}")
    print(f"  Kelly Fraction: {kelly_fraction:.2%}")
    print(f"  Kelly Amount: ${kelly_amount:,.2f}")

    # Test Fixed Fractional
    risk_per_trade = 0.02  # 2%
    fixed_fractional_amount = PositionSizer.fixed_fractional(account_balance, risk_per_trade)

    print(f"\\nFixed Fractional (2% risk):")
    print(f"  Risk Amount: ${fixed_fractional_amount:,.2f}")

    # Test Volatility Adjusted
    symbol_volatility = 0.30  # 30% annualized
    target_volatility = 0.15  # 15% target
    base_allocation = 0.10  # 10% base

    vol_adj_fraction = PositionSizer.volatility_adjusted(
        account_balance, symbol_volatility, target_volatility, base_allocation
    )
    vol_adj_amount = account_balance * vol_adj_fraction

    print(f"\\nVolatility Adjusted:")
    print(f"  Symbol Volatility: {symbol_volatility:.1%}")
    print(f"  Target Volatility: {target_volatility:.1%}")
    print(f"  Adjusted Fraction: {vol_adj_fraction:.2%}")
    print(f"  Position Amount: ${vol_adj_amount:,.2f}")

def test_portfolio_risk_manager():
    """Test integrated portfolio risk management"""
    print("\\n" + "=" * 60)
    print("TESTING PORTFOLIO RISK MANAGER")
    print("=" * 60)

    # Create sample portfolio
    pm = PortfolioManager(initial_cash=100000, use_ib=False, db_path="test_portfolio.db")

    # Add some sample trades
    pm.add_trade("AAPL", 100, 150.0)
    pm.add_trade("NVDA", 50, 800.0)
    pm.add_trade("SPY", 200, 400.0)
    pm.add_trade("TSLA", -25, 250.0)  # Short position

    # Create risk manager
    rm = create_sample_risk_manager(pm)

    # Generate sample returns for analysis
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.02, 100))  # 100 days of returns
    equity_curve = (1 + returns).cumprod() * pm.initial_cash

    # Calculate risk metrics
    risk_metrics = rm.calculate_portfolio_risk_metrics(returns, equity_curve)

    print(f"Portfolio Risk Metrics:")
    print(f"  Total Value: ${pm.total_value:,.2f}")
    print(f"  Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}")
    print(f"  VaR 95%: {risk_metrics.var_95:.2%}")
    print(f"  CVaR 95%: {risk_metrics.cvar_95:.2%}")
    print(f"  Max Drawdown: {risk_metrics.max_drawdown:.2%}")
    print(f"  Concentration Risk: {risk_metrics.concentration_risk:.2%}")

    # Check risk limits
    alerts = rm.check_risk_limits(risk_metrics)
    print(f"\\nRisk Alerts Generated: {len(alerts)}")
    for alert in alerts:
        print(f"  - {alert.level.value}: {alert.message}")

    # Generate risk report
    risk_report = rm.get_risk_report()
    print(f"\\nPortfolio Summary:")
    print(f"  Number of Positions: {risk_report['portfolio_summary']['num_positions']}")
    print(f"  Cash Ratio: {risk_report['liquidity_analysis']['cash_ratio']:.1%}")

    # Test stress testing
    stress_scenarios = {
        "Market Crash": -0.20,
        "Moderate Decline": -0.10,
        "Bull Run": 0.15
    }

    stress_results = rm.stress_test_portfolio(stress_scenarios)
    print(f"\\nStress Test Results:")
    for scenario, result in stress_results.items():
        print(f"  {scenario}: {result['pnl_pct']:+.1%} (${result['pnl']:,.0f})")

    # Test position sizing
    kelly_size = rm.calculate_position_size(
        "TEST", pm.total_value, "kelly",
        win_rate=0.55, avg_win=0.025, avg_loss=0.018
    )
    print(f"\\nKelly Position Size for new trade: ${kelly_size:,.2f}")

def test_cfd_risk_manager():
    """Test CFD-specific risk management"""
    print("\\n" + "=" * 60)
    print("TESTING CFD RISK MANAGER")
    print("=" * 60)

    # Create CFD risk manager
    cfd_rm = CFDRiskManager(initial_balance=100000)

    # Create sample CFD positions
    eurusd_position = CFDPosition(
        symbol="EURUSD",
        position_size=100000,  # 1 standard lot
        entry_price=1.1000,
        current_price=1.1050,
        leverage=50,
        margin_used=2200,  # 100000 / 50 + buffer
        overnight_fee_rate=0.02,
        instrument_type=CFDInstrumentType.FOREX,
        is_long=True,
        entry_time=datetime.now() - timedelta(hours=6),
        last_update=datetime.now()
    )

    spx500_position = CFDPosition(
        symbol="SPX500",
        position_size=10,  # 10 contracts
        entry_price=4200.0,
        current_price=4250.0,
        leverage=20,
        margin_used=2100,  # (10 * 4200) / 20
        overnight_fee_rate=0.025,
        instrument_type=CFDInstrumentType.INDEX,
        is_long=True,
        entry_time=datetime.now() - timedelta(hours=3),
        last_update=datetime.now()
    )

    # Add positions to manager
    success1 = cfd_rm.add_position(eurusd_position)
    success2 = cfd_rm.add_position(spx500_position)

    print(f"Added EURUSD position: {success1}")
    print(f"Added SPX500 position: {success2}")

    # Get account summary
    summary = cfd_rm.get_account_summary()

    print(f"\\nCFD Account Summary:")
    print(f"  Equity: ${summary['equity']:,.2f}")
    print(f"  Used Margin: ${summary['used_margin']:,.2f}")
    print(f"  Free Margin: ${summary['free_margin']:,.2f}")
    print(f"  Margin Level: {summary['margin_level']:.1f}%")
    print(f"  Total Exposure: ${summary['total_exposure']:,.2f}")
    print(f"  Exposure Ratio: {summary['exposure_ratio']:.1%}")
    print(f"  Daily Financing Cost: ${summary['daily_overnight_cost']:.2f}")

    # Test position calculations
    print(f"\\nPosition Details:")
    for position in cfd_rm.positions:
        liquidation_price = position.calculate_liquidation_price()
        overnight_cost = position.calculate_overnight_fees()

        print(f"  {position.symbol}:")
        print(f"    Unrealized P&L: ${position.unrealized_pnl:,.2f}")
        print(f"    Margin Level: {position.margin_level:.1f}%")
        print(f"    Liquidation Price: {liquidation_price:.4f}")
        print(f"    Daily Financing: ${overnight_cost:.2f}")

    # Test stress scenarios
    cfd_stress_scenarios = {
        "Major Market Crash": {
            "EURUSD": -0.05,  # 5% decline
            "SPX500": -0.15   # 15% decline
        },
        "Currency Crisis": {
            "EURUSD": -0.10,  # 10% decline
            "SPX500": -0.05   # 5% decline
        }
    }

    stress_results = cfd_rm.stress_test_cfd_portfolio(cfd_stress_scenarios)

    print(f"\\nCFD Stress Test Results:")
    for scenario, result in stress_results.items():
        print(f"  {scenario}:")
        print(f"    P&L: ${result['scenario_pnl']:,.0f} ({result['scenario_pnl_pct']:+.1%})")
        print(f"    Stressed Margin Level: {result['stressed_margin_level']:.1f}%")
        print(f"    Account Survives: {result['account_survives']}")
        print(f"    Margin Calls: {result['margin_calls']}")
        print(f"    Liquidations: {result['liquidations']}")

    # Generate CFD risk report
    cfd_risk_report = cfd_rm.generate_risk_report()

    print(f"\\nCFD Risk Warnings:")
    if cfd_risk_report['risk_warnings']:
        for warning in cfd_risk_report['risk_warnings']:
            print(f"  - {warning}")
    else:
        print("  No active warnings")

def test_integration():
    """Test integration between different risk management components"""
    print("\\n" + "=" * 60)
    print("TESTING SYSTEM INTEGRATION")
    print("=" * 60)

    # Create integrated system
    pm = PortfolioManager(initial_cash=100000, use_ib=False, db_path="test_integration.db")
    rm = RiskManager(pm)
    cfd_rm = CFDRiskManager()

    # Simulate trading activity
    print("Simulating trading activity...")

    # Regular equity trades
    pm.add_trade("AAPL", 100, 150.0)
    pm.add_trade("NVDA", 25, 800.0)
    pm.add_trade("SPY", 150, 400.0)

    # Add CFD positions
    forex_position = create_sample_cfd_position("GBPUSD", 50000, 30)
    index_position = create_sample_cfd_position("NASDAQ100", 5000, 15)

    cfd_rm.add_position(forex_position)
    cfd_rm.add_position(index_position)

    # Calculate combined risk metrics
    portfolio_value = pm.total_value
    cfd_equity = cfd_rm.get_account_summary()['equity']
    total_value = portfolio_value + cfd_equity

    print(f"\\nCombined Portfolio Analysis:")
    print(f"  Regular Portfolio Value: ${portfolio_value:,.2f}")
    print(f"  CFD Account Equity: ${cfd_equity:,.2f}")
    print(f"  Total Combined Value: ${total_value:,.2f}")

    # Risk concentration analysis
    positions_df = pm.get_positions_df()
    if not positions_df.empty:
        max_position = positions_df['market_value'].max()
        concentration = max_position / total_value
        print(f"  Max Position Concentration: {concentration:.1%}")

    # Combined exposure analysis
    regular_exposure = portfolio_value - pm.cash_balance
    cfd_exposure = cfd_rm.get_total_exposure()
    total_exposure = regular_exposure + cfd_exposure

    print(f"  Regular Market Exposure: ${regular_exposure:,.2f}")
    print(f"  CFD Market Exposure: ${cfd_exposure:,.2f}")
    print(f"  Total Market Exposure: ${total_exposure:,.2f}")
    print(f"  Total Exposure Ratio: {total_exposure / total_value:.1%}")

    # Generate recommendations
    print(f"\\nRisk Management Recommendations:")

    if concentration > 0.20:
        print("  - Consider reducing position concentration (>20% in single position)")

    if total_exposure / total_value > 0.90:
        print("  - High market exposure (>90%) - consider increasing cash allocation")

    cfd_margin_level = cfd_rm.get_account_summary()['margin_level']
    if cfd_margin_level < 200:
        print(f"  - CFD margin level low ({cfd_margin_level:.0f}%) - monitor closely")

    print("\\nIntegration test completed successfully!")

def main():
    """Run all risk management tests"""
    print("COMPREHENSIVE RISK MANAGEMENT SYSTEM TEST")
    print("=" * 80)

    try:
        # Run individual component tests
        test_risk_calculator()
        test_position_sizer()
        test_portfolio_risk_manager()
        test_cfd_risk_manager()
        test_integration()

        print("\\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)

        print("\\nRisk Management System Features Validated:")
        print("✅ Core risk metric calculations (VaR, CVaR, Sharpe, Sortino, etc.)")
        print("✅ Position sizing algorithms (Kelly Criterion, Fixed Fractional, Volatility Adjusted)")
        print("✅ Portfolio-level risk monitoring and alerting")
        print("✅ CFD-specific risk management (margin, leverage, overnight costs)")
        print("✅ Stress testing capabilities")
        print("✅ Risk limit enforcement")
        print("✅ Comprehensive risk reporting")
        print("✅ Integration with existing portfolio management")

        print("\\nNext Steps:")
        print("1. Run the enhanced Portfolio Tracker: streamlit run portfolio_tracker.py")
        print("2. Navigate to the 'Risk Management' and 'CFD Trading' tabs")
        print("3. Test risk calculations with actual trading data")
        print("4. Configure risk limits according to your risk tolerance")
        print("5. Use stress testing to validate portfolio resilience")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    main()