"""
Advanced Risk Management System
Comprehensive risk management framework for quantitative trading with CFD support
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import warnings
from scipy import stats
from scipy.optimize import minimize_scalar
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class RiskAlert:
    """Risk alert notification"""
    timestamp: datetime
    risk_type: str
    level: RiskLevel
    message: str
    symbol: Optional[str] = None
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    recommended_action: Optional[str] = None

@dataclass
class RiskMetrics:
    """Container for risk metrics"""
    # Return-based metrics
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None

    # Risk metrics
    var_95: Optional[float] = None  # 95% Value at Risk
    var_99: Optional[float] = None  # 99% Value at Risk
    cvar_95: Optional[float] = None  # 95% Conditional VaR
    cvar_99: Optional[float] = None  # 99% Conditional VaR

    # Drawdown metrics
    max_drawdown: Optional[float] = None
    max_drawdown_duration: Optional[int] = None
    current_drawdown: Optional[float] = None

    # Volatility metrics
    volatility_daily: Optional[float] = None
    volatility_annualized: Optional[float] = None

    # Position metrics
    concentration_risk: Optional[float] = None  # Largest position as % of portfolio
    diversification_ratio: Optional[float] = None

    # Beta and correlation
    beta_to_market: Optional[float] = None
    correlation_to_market: Optional[float] = None

    # Additional metrics
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    tail_ratio: Optional[float] = None

    calculation_date: datetime = None

    def __post_init__(self):
        if self.calculation_date is None:
            self.calculation_date = datetime.now()

class PositionSizer:
    """Position sizing algorithms"""

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float,
                       max_fraction: float = 0.25) -> float:
        """
        Calculate Kelly Criterion position size

        Args:
            win_rate: Probability of winning trades (0-1)
            avg_win: Average winning amount
            avg_loss: Average losing amount (positive number)
            max_fraction: Maximum fraction of capital to risk (default 25%)

        Returns:
            Optimal fraction of capital to allocate
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0

        win_loss_ratio = avg_win / avg_loss
        kelly_fraction = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Cap at maximum fraction to prevent over-leverage
        return max(0.0, min(kelly_fraction, max_fraction))

    @staticmethod
    def fixed_fractional(account_balance: float, risk_per_trade: float = 0.02) -> float:
        """
        Fixed fractional position sizing

        Args:
            account_balance: Current account balance
            risk_per_trade: Fraction of account to risk per trade (default 2%)

        Returns:
            Dollar amount to risk
        """
        return account_balance * risk_per_trade

    @staticmethod
    def volatility_adjusted(account_balance: float, symbol_volatility: float,
                          target_volatility: float = 0.15, base_allocation: float = 0.1) -> float:
        """
        Volatility-adjusted position sizing

        Args:
            account_balance: Current account balance
            symbol_volatility: Annualized volatility of the symbol
            target_volatility: Target portfolio volatility
            base_allocation: Base allocation percentage

        Returns:
            Position size as fraction of account
        """
        if symbol_volatility <= 0:
            return base_allocation

        volatility_scalar = target_volatility / symbol_volatility
        adjusted_allocation = base_allocation * volatility_scalar

        # Cap at reasonable limits
        return max(0.01, min(adjusted_allocation, 0.5))

class RiskCalculator:
    """Core risk calculation engine"""

    @staticmethod
    def calculate_var(returns: pd.Series, confidence_level: float = 0.95,
                     method: str = "historical") -> float:
        """
        Calculate Value at Risk (VaR)

        Args:
            returns: Series of returns
            confidence_level: Confidence level (0.95 or 0.99)
            method: "historical", "parametric", or "monte_carlo"

        Returns:
            VaR value (positive number representing loss)
        """
        if len(returns) == 0:
            return np.nan

        if method == "historical":
            return -np.percentile(returns.dropna(), (1 - confidence_level) * 100)
        elif method == "parametric":
            mean = returns.mean()
            std = returns.std()
            z_score = stats.norm.ppf(1 - confidence_level)
            return -(mean + z_score * std)
        else:
            raise ValueError("Method must be 'historical' or 'parametric'")

    @staticmethod
    def calculate_cvar(returns: pd.Series, confidence_level: float = 0.95) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall)

        Args:
            returns: Series of returns
            confidence_level: Confidence level

        Returns:
            CVaR value (positive number representing expected loss beyond VaR)
        """
        if len(returns) == 0:
            return np.nan

        var_threshold = -RiskCalculator.calculate_var(returns, confidence_level)
        tail_returns = returns[returns <= var_threshold]

        if len(tail_returns) == 0:
            return np.nan

        return -tail_returns.mean()

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> Tuple[float, int]:
        """
        Calculate maximum drawdown and duration

        Args:
            equity_curve: Series of portfolio values over time

        Returns:
            Tuple of (max_drawdown_pct, duration_in_periods)
        """
        if len(equity_curve) == 0:
            return np.nan, 0

        # Calculate running maximum
        running_max = equity_curve.expanding().max()

        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max

        # Maximum drawdown
        max_dd = drawdown.min()

        # Calculate duration
        max_dd_duration = 0
        current_dd_duration = 0

        for dd in drawdown:
            if dd < 0:
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)
            else:
                current_dd_duration = 0

        return abs(max_dd), max_dd_duration

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio (annualized)

        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate (annualized)

        Returns:
            Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return np.nan

        # Annualize returns (assuming daily returns)
        excess_return = returns.mean() * 252 - risk_free_rate
        volatility = returns.std() * np.sqrt(252)

        return excess_return / volatility

    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (focusing on downside deviation)

        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate (annualized)

        Returns:
            Sortino ratio
        """
        if len(returns) == 0:
            return np.nan

        # Annualized excess return
        excess_return = returns.mean() * 252 - risk_free_rate

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return np.inf if excess_return > 0 else np.nan

        downside_deviation = downside_returns.std() * np.sqrt(252)

        return excess_return / downside_deviation

    @staticmethod
    def calculate_calmar_ratio(returns: pd.Series, equity_curve: pd.Series) -> float:
        """
        Calculate Calmar ratio (CAGR / Max Drawdown)

        Args:
            returns: Series of returns
            equity_curve: Series of portfolio values

        Returns:
            Calmar ratio
        """
        if len(returns) == 0 or len(equity_curve) == 0:
            return np.nan

        # Calculate CAGR
        total_periods = len(returns)
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0])
        cagr = (total_return ** (252 / total_periods)) - 1

        # Calculate max drawdown
        max_dd, _ = RiskCalculator.calculate_max_drawdown(equity_curve)

        if max_dd == 0:
            return np.inf if cagr > 0 else np.nan

        return cagr / max_dd

class CFDRiskManager:
    """Specialized risk management for CFD trading"""

    def __init__(self, max_leverage: float = 10.0, margin_call_level: float = 0.5):
        self.max_leverage = max_leverage
        self.margin_call_level = margin_call_level

    def calculate_margin_requirement(self, position_value: float, leverage: float) -> float:
        """
        Calculate margin requirement for CFD position

        Args:
            position_value: Notional value of position
            leverage: Applied leverage

        Returns:
            Required margin
        """
        return abs(position_value) / leverage

    def calculate_maintenance_margin(self, position_value: float,
                                   maintenance_rate: float = 0.005) -> float:
        """
        Calculate maintenance margin requirement

        Args:
            position_value: Current market value of position
            maintenance_rate: Maintenance margin rate (default 0.5%)

        Returns:
            Maintenance margin required
        """
        return abs(position_value) * maintenance_rate

    def check_margin_call(self, account_equity: float, used_margin: float,
                         maintenance_margin: float) -> bool:
        """
        Check if account is subject to margin call

        Args:
            account_equity: Current account equity
            used_margin: Currently used margin
            maintenance_margin: Required maintenance margin

        Returns:
            True if margin call triggered
        """
        margin_level = account_equity / used_margin if used_margin > 0 else float('inf')
        return margin_level <= self.margin_call_level

    def calculate_liquidation_price(self, entry_price: float, position_size: float,
                                  account_equity: float, leverage: float,
                                  is_long: bool = True) -> float:
        """
        Calculate liquidation price for CFD position

        Args:
            entry_price: Entry price of position
            position_size: Size of position (positive for long, negative for short)
            account_equity: Current account equity
            leverage: Position leverage
            is_long: True for long position, False for short

        Returns:
            Price at which position will be liquidated
        """
        margin_used = abs(position_size * entry_price) / leverage

        if is_long:
            # For long positions, liquidation occurs when equity falls to maintenance level
            max_loss = account_equity * (1 - self.margin_call_level)
            liquidation_price = entry_price - (max_loss / abs(position_size))
        else:
            # For short positions
            max_loss = account_equity * (1 - self.margin_call_level)
            liquidation_price = entry_price + (max_loss / abs(position_size))

        return max(0, liquidation_price)

class RiskManager:
    """Main risk management system"""

    def __init__(self, portfolio_manager=None, db_path: str = "risk_data.db"):
        self.portfolio_manager = portfolio_manager
        self.db_path = Path(db_path)
        self.alerts: List[RiskAlert] = []
        self.risk_limits = self._default_risk_limits()
        self.cfd_risk_manager = CFDRiskManager()

        # Initialize database
        self._init_risk_database()

    def _default_risk_limits(self) -> Dict[str, float]:
        """Default risk limits"""
        return {
            'max_portfolio_var_daily': 0.02,  # 2% daily VaR
            'max_position_concentration': 0.20,  # 20% max single position
            'max_sector_concentration': 0.30,  # 30% max sector exposure
            'max_drawdown_alert': 0.10,  # 10% drawdown alert
            'max_drawdown_stop': 0.15,  # 15% stop all trading
            'min_sharpe_ratio': 0.5,  # Minimum acceptable Sharpe
            'max_correlation_threshold': 0.8,  # Maximum correlation between positions
            'max_leverage': 5.0,  # Maximum leverage for CFDs
            'min_liquidity_ratio': 0.1,  # Minimum cash as % of portfolio
        }

    def _init_risk_database(self):
        """Initialize risk management database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS risk_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calculation_date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    symbol TEXT,
                    timeframe TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS risk_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    risk_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    symbol TEXT,
                    metric_name TEXT,
                    current_value REAL,
                    threshold REAL,
                    recommended_action TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS risk_limits (
                    limit_name TEXT PRIMARY KEY,
                    limit_value REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def update_risk_limits(self, new_limits: Dict[str, float]):
        """Update risk limits"""
        self.risk_limits.update(new_limits)

        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            for limit_name, limit_value in new_limits.items():
                conn.execute('''
                    INSERT OR REPLACE INTO risk_limits (limit_name, limit_value)
                    VALUES (?, ?)
                ''', (limit_name, limit_value))

    def calculate_portfolio_risk_metrics(self, returns: pd.Series = None,
                                       equity_curve: pd.Series = None,
                                       benchmark_returns: pd.Series = None) -> RiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics

        Args:
            returns: Portfolio returns series
            equity_curve: Portfolio equity curve
            benchmark_returns: Benchmark returns for beta calculation

        Returns:
            RiskMetrics object with calculated metrics
        """
        if returns is None or len(returns) == 0:
            logger.warning("No returns data provided for risk calculation")
            return RiskMetrics()

        metrics = RiskMetrics()

        try:
            # Basic risk metrics
            metrics.var_95 = RiskCalculator.calculate_var(returns, 0.95)
            metrics.var_99 = RiskCalculator.calculate_var(returns, 0.99)
            metrics.cvar_95 = RiskCalculator.calculate_cvar(returns, 0.95)
            metrics.cvar_99 = RiskCalculator.calculate_cvar(returns, 0.99)

            # Ratios
            metrics.sharpe_ratio = RiskCalculator.calculate_sharpe_ratio(returns)
            metrics.sortino_ratio = RiskCalculator.calculate_sortino_ratio(returns)

            # Volatility
            metrics.volatility_daily = returns.std()
            metrics.volatility_annualized = returns.std() * np.sqrt(252)

            # Drawdown metrics
            if equity_curve is not None and len(equity_curve) > 0:
                max_dd, dd_duration = RiskCalculator.calculate_max_drawdown(equity_curve)
                metrics.max_drawdown = max_dd
                metrics.max_drawdown_duration = dd_duration
                metrics.calmar_ratio = RiskCalculator.calculate_calmar_ratio(returns, equity_curve)

                # Current drawdown
                current_peak = equity_curve.expanding().max().iloc[-1]
                current_value = equity_curve.iloc[-1]
                metrics.current_drawdown = abs((current_value - current_peak) / current_peak)

            # Portfolio concentration (if portfolio manager available)
            if self.portfolio_manager:
                positions_df = self.portfolio_manager.get_positions_df()
                if not positions_df.empty:
                    total_value = self.portfolio_manager.total_value
                    if total_value > 0:
                        position_weights = positions_df['market_value'].abs() / total_value
                        metrics.concentration_risk = position_weights.max()

                        # Diversification ratio (simplified)
                        n_positions = len(positions_df)
                        if n_positions > 1:
                            equal_weight = 1.0 / n_positions
                            metrics.diversification_ratio = equal_weight / position_weights.max()

            # Beta and correlation to benchmark
            if benchmark_returns is not None and len(benchmark_returns) > 0:
                aligned_data = pd.DataFrame({
                    'portfolio': returns,
                    'benchmark': benchmark_returns
                }).dropna()

                if len(aligned_data) > 10:  # Minimum data points for meaningful calculation
                    metrics.correlation_to_market = aligned_data['portfolio'].corr(aligned_data['benchmark'])

                    # Calculate beta using linear regression
                    x = aligned_data['benchmark'].values
                    y = aligned_data['portfolio'].values
                    if np.var(x) > 0:
                        metrics.beta_to_market = np.cov(x, y)[0, 1] / np.var(x)

            # Higher moment statistics
            metrics.skewness = returns.skew()
            metrics.kurtosis = returns.kurtosis()

            # Tail ratio (95th percentile / 5th percentile of returns)
            p95 = np.percentile(returns.dropna(), 95)
            p5 = np.percentile(returns.dropna(), 5)
            if p5 != 0:
                metrics.tail_ratio = p95 / abs(p5)

        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")

        # Save metrics to database
        self._save_risk_metrics(metrics)

        return metrics

    def _save_risk_metrics(self, metrics: RiskMetrics):
        """Save risk metrics to database"""
        with sqlite3.connect(self.db_path) as conn:
            metrics_data = [
                ('sharpe_ratio', metrics.sharpe_ratio),
                ('sortino_ratio', metrics.sortino_ratio),
                ('calmar_ratio', metrics.calmar_ratio),
                ('var_95', metrics.var_95),
                ('var_99', metrics.var_99),
                ('cvar_95', metrics.cvar_95),
                ('cvar_99', metrics.cvar_99),
                ('max_drawdown', metrics.max_drawdown),
                ('current_drawdown', metrics.current_drawdown),
                ('volatility_daily', metrics.volatility_daily),
                ('volatility_annualized', metrics.volatility_annualized),
                ('concentration_risk', metrics.concentration_risk),
                ('beta_to_market', metrics.beta_to_market),
                ('correlation_to_market', metrics.correlation_to_market),
                ('skewness', metrics.skewness),
                ('kurtosis', metrics.kurtosis),
            ]

            for metric_name, value in metrics_data:
                if value is not None and not np.isnan(value):
                    conn.execute('''
                        INSERT INTO risk_metrics
                        (calculation_date, metric_name, value)
                        VALUES (?, ?, ?)
                    ''', (metrics.calculation_date.isoformat(), metric_name, value))

    def check_risk_limits(self, metrics: RiskMetrics) -> List[RiskAlert]:
        """
        Check risk metrics against defined limits and generate alerts

        Args:
            metrics: Calculated risk metrics

        Returns:
            List of risk alerts
        """
        alerts = []

        # VaR limit check
        if (metrics.var_95 is not None and
            metrics.var_95 > self.risk_limits['max_portfolio_var_daily']):
            alert = RiskAlert(
                timestamp=datetime.now(),
                risk_type="VAR_BREACH",
                level=RiskLevel.HIGH,
                message=f"Daily VaR ({metrics.var_95:.2%}) exceeds limit ({self.risk_limits['max_portfolio_var_daily']:.2%})",
                metric_name="var_95",
                current_value=metrics.var_95,
                threshold=self.risk_limits['max_portfolio_var_daily'],
                recommended_action="Reduce position sizes or hedge portfolio"
            )
            alerts.append(alert)

        # Concentration risk check
        if (metrics.concentration_risk is not None and
            metrics.concentration_risk > self.risk_limits['max_position_concentration']):
            alert = RiskAlert(
                timestamp=datetime.now(),
                risk_type="CONCENTRATION_RISK",
                level=RiskLevel.MEDIUM,
                message=f"Position concentration ({metrics.concentration_risk:.2%}) exceeds limit ({self.risk_limits['max_position_concentration']:.2%})",
                metric_name="concentration_risk",
                current_value=metrics.concentration_risk,
                threshold=self.risk_limits['max_position_concentration'],
                recommended_action="Diversify portfolio by reducing largest positions"
            )
            alerts.append(alert)

        # Drawdown checks
        if (metrics.current_drawdown is not None):
            if metrics.current_drawdown > self.risk_limits['max_drawdown_stop']:
                alert = RiskAlert(
                    timestamp=datetime.now(),
                    risk_type="CRITICAL_DRAWDOWN",
                    level=RiskLevel.CRITICAL,
                    message=f"Current drawdown ({metrics.current_drawdown:.2%}) exceeds stop limit ({self.risk_limits['max_drawdown_stop']:.2%})",
                    metric_name="current_drawdown",
                    current_value=metrics.current_drawdown,
                    threshold=self.risk_limits['max_drawdown_stop'],
                    recommended_action="HALT ALL TRADING - Review strategy and risk controls"
                )
                alerts.append(alert)
            elif metrics.current_drawdown > self.risk_limits['max_drawdown_alert']:
                alert = RiskAlert(
                    timestamp=datetime.now(),
                    risk_type="DRAWDOWN_WARNING",
                    level=RiskLevel.HIGH,
                    message=f"Current drawdown ({metrics.current_drawdown:.2%}) exceeds warning limit ({self.risk_limits['max_drawdown_alert']:.2%})",
                    metric_name="current_drawdown",
                    current_value=metrics.current_drawdown,
                    threshold=self.risk_limits['max_drawdown_alert'],
                    recommended_action="Reduce risk exposure and review positions"
                )
                alerts.append(alert)

        # Sharpe ratio check
        if (metrics.sharpe_ratio is not None and
            metrics.sharpe_ratio < self.risk_limits['min_sharpe_ratio']):
            alert = RiskAlert(
                timestamp=datetime.now(),
                risk_type="LOW_RISK_ADJUSTED_RETURN",
                level=RiskLevel.MEDIUM,
                message=f"Sharpe ratio ({metrics.sharpe_ratio:.2f}) below minimum ({self.risk_limits['min_sharpe_ratio']:.2f})",
                metric_name="sharpe_ratio",
                current_value=metrics.sharpe_ratio,
                threshold=self.risk_limits['min_sharpe_ratio'],
                recommended_action="Review strategy performance and consider adjustments"
            )
            alerts.append(alert)

        # Save alerts to database and add to instance
        for alert in alerts:
            self._save_alert(alert)
            self.alerts.append(alert)

        return alerts

    def _save_alert(self, alert: RiskAlert):
        """Save risk alert to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO risk_alerts
                (timestamp, risk_type, level, message, symbol, metric_name,
                 current_value, threshold, recommended_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.timestamp.isoformat(),
                alert.risk_type,
                alert.level.value,
                alert.message,
                alert.symbol,
                alert.metric_name,
                alert.current_value,
                alert.threshold,
                alert.recommended_action
            ))

    def calculate_position_size(self, symbol: str, account_balance: float,
                              method: str = "kelly", **kwargs) -> float:
        """
        Calculate optimal position size for a symbol

        Args:
            symbol: Trading symbol
            account_balance: Current account balance
            method: Position sizing method ("kelly", "fixed_fractional", "volatility_adjusted")
            **kwargs: Additional parameters for the method

        Returns:
            Recommended position size in dollars
        """
        if method == "kelly":
            # Get historical performance for Kelly calculation
            win_rate = kwargs.get('win_rate', 0.55)
            avg_win = kwargs.get('avg_win', 0.02)
            avg_loss = kwargs.get('avg_loss', 0.015)
            max_fraction = kwargs.get('max_fraction', 0.25)

            kelly_fraction = PositionSizer.kelly_criterion(win_rate, avg_win, avg_loss, max_fraction)
            return account_balance * kelly_fraction

        elif method == "fixed_fractional":
            risk_per_trade = kwargs.get('risk_per_trade', 0.02)
            return PositionSizer.fixed_fractional(account_balance, risk_per_trade)

        elif method == "volatility_adjusted":
            symbol_volatility = kwargs.get('symbol_volatility', 0.25)
            target_volatility = kwargs.get('target_volatility', 0.15)
            base_allocation = kwargs.get('base_allocation', 0.1)

            allocation_fraction = PositionSizer.volatility_adjusted(
                account_balance, symbol_volatility, target_volatility, base_allocation
            )
            return account_balance * allocation_fraction

        else:
            raise ValueError(f"Unknown position sizing method: {method}")

    def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report"""
        if not self.portfolio_manager:
            return {"error": "No portfolio manager available"}

        # Get portfolio data
        positions_df = self.portfolio_manager.get_positions_df()
        portfolio_summary = self.portfolio_manager.get_portfolio_summary()

        # Calculate recent returns if we have trade history
        trades_df = self.portfolio_manager.get_trades_df()

        report = {
            "report_date": datetime.now().isoformat(),
            "portfolio_summary": portfolio_summary,
            "risk_limits": self.risk_limits,
            "active_alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "type": alert.risk_type,
                    "level": alert.level.value,
                    "message": alert.message,
                    "action": alert.recommended_action
                } for alert in self.alerts[-10:]  # Last 10 alerts
            ],
            "position_analysis": {},
            "liquidity_analysis": {
                "cash_ratio": portfolio_summary['cash_balance'] / portfolio_summary['total_value'] if portfolio_summary['total_value'] > 0 else 0,
                "meets_liquidity_requirement": (portfolio_summary['cash_balance'] / portfolio_summary['total_value']) >= self.risk_limits['min_liquidity_ratio'] if portfolio_summary['total_value'] > 0 else False
            }
        }

        # Position analysis
        if not positions_df.empty:
            total_value = portfolio_summary['total_value']
            position_analysis = {}

            for _, pos in positions_df.iterrows():
                weight = abs(pos['market_value']) / total_value if total_value > 0 else 0
                position_analysis[pos['symbol']] = {
                    "weight": weight,
                    "unrealized_pnl_pct": pos['unrealized_pnl_pct'],
                    "risk_level": "HIGH" if weight > 0.15 else "MEDIUM" if weight > 0.1 else "LOW"
                }

            report["position_analysis"] = position_analysis

            # Overall concentration risk
            max_weight = max([pos["weight"] for pos in position_analysis.values()]) if position_analysis else 0
            report["concentration_risk"] = {
                "max_position_weight": max_weight,
                "exceeds_limit": max_weight > self.risk_limits['max_position_concentration']
            }

        return report

    def stress_test_portfolio(self, scenarios: Dict[str, float]) -> Dict[str, float]:
        """
        Perform stress testing on portfolio

        Args:
            scenarios: Dictionary of scenario names and market moves (e.g., {"market_crash": -0.20})

        Returns:
            Dictionary of scenario results
        """
        if not self.portfolio_manager:
            return {}

        positions_df = self.portfolio_manager.get_positions_df()
        if positions_df.empty:
            return {}

        current_value = self.portfolio_manager.total_value
        results = {}

        for scenario_name, market_move in scenarios.items():
            # Simplified stress test assuming all positions move with market
            # In practice, you'd use beta, correlations, and sector-specific moves
            stressed_positions_value = 0

            for _, pos in positions_df.iterrows():
                # Apply stress scenario (simplified - assumes beta of 1 for all positions)
                stressed_price = pos['current_price'] * (1 + market_move)
                stressed_value = pos['quantity'] * stressed_price
                stressed_positions_value += stressed_value

            stressed_portfolio_value = stressed_positions_value + self.portfolio_manager.cash_balance
            pnl = stressed_portfolio_value - current_value
            pnl_pct = pnl / current_value if current_value > 0 else 0

            results[scenario_name] = {
                "portfolio_value": stressed_portfolio_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "market_move": market_move
            }

        return results

    def calculate_correlation_matrix(self, symbols: List[str],
                                   lookback_days: int = 252) -> pd.DataFrame:
        """
        Calculate correlation matrix for portfolio positions

        Args:
            symbols: List of symbols to calculate correlations for
            lookback_days: Number of days for correlation calculation

        Returns:
            Correlation matrix DataFrame
        """
        try:
            import yfinance as yf

            # Get historical data for all symbols
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 50)  # Buffer for weekends

            returns_data = {}

            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist_data = ticker.history(start=start_date, end=end_date)

                    if not hist_data.empty:
                        # Calculate daily returns
                        daily_returns = hist_data['Close'].pct_change().dropna()
                        returns_data[symbol] = daily_returns

                except Exception as e:
                    logger.warning(f"Failed to get data for {symbol}: {e}")

            if len(returns_data) < 2:
                logger.warning("Insufficient data for correlation calculation")
                return pd.DataFrame()

            # Create DataFrame and calculate correlation
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()

            return correlation_matrix

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return pd.DataFrame()

    def get_correlation_risks(self, correlation_threshold: float = 0.7) -> List[RiskAlert]:
        """
        Identify correlation-based risks in portfolio

        Args:
            correlation_threshold: Correlation level to trigger alerts

        Returns:
            List of correlation risk alerts
        """
        alerts = []

        if not self.portfolio_manager:
            return alerts

        positions_df = self.portfolio_manager.get_positions_df()

        if positions_df.empty or len(positions_df) < 2:
            return alerts

        symbols = positions_df['symbol'].tolist()
        correlation_matrix = self.calculate_correlation_matrix(symbols)

        if correlation_matrix.empty:
            return alerts

        # Check for high correlations
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i < j:  # Avoid duplicates and self-correlation
                    try:
                        correlation = correlation_matrix.loc[symbol1, symbol2]

                        if abs(correlation) > correlation_threshold:
                            # Calculate combined exposure
                            pos1_value = positions_df[positions_df['symbol'] == symbol1]['market_value'].iloc[0]
                            pos2_value = positions_df[positions_df['symbol'] == symbol2]['market_value'].iloc[0]
                            combined_exposure = (abs(pos1_value) + abs(pos2_value)) / self.portfolio_manager.total_value

                            alert = RiskAlert(
                                timestamp=datetime.now(),
                                risk_type="HIGH_CORRELATION",
                                level=RiskLevel.MEDIUM if combined_exposure < 0.3 else RiskLevel.HIGH,
                                message=f"High correlation ({correlation:.2f}) between {symbol1} and {symbol2}. Combined exposure: {combined_exposure:.1%}",
                                recommended_action=f"Consider reducing exposure to correlated positions"
                            )
                            alerts.append(alert)

                    except Exception as e:
                        logger.warning(f"Error processing correlation for {symbol1}/{symbol2}: {e}")

        return alerts

    def calculate_portfolio_concentration_risk(self) -> Dict[str, Any]:
        """
        Calculate detailed concentration risk metrics

        Returns:
            Dictionary with concentration risk analysis
        """
        if not self.portfolio_manager:
            return {}

        positions_df = self.portfolio_manager.get_positions_df()

        if positions_df.empty:
            return {}

        total_value = self.portfolio_manager.total_value

        # Position concentration
        position_weights = positions_df['market_value'].abs() / total_value

        # Herfindahl-Hirschman Index (HHI) for concentration
        hhi = (position_weights ** 2).sum()

        # Effective number of positions
        effective_positions = 1 / hhi if hhi > 0 else 0

        # Top 3 concentration
        top3_concentration = position_weights.nlargest(3).sum()

        # Sector concentration (simplified - would need sector data in practice)
        # This is a placeholder implementation
        sector_exposure = {"Technology": 0.4, "Finance": 0.3, "Healthcare": 0.2, "Other": 0.1}
        max_sector_exposure = max(sector_exposure.values())

        return {
            "position_concentration": {
                "largest_position": position_weights.max(),
                "top3_concentration": top3_concentration,
                "hhi_index": hhi,
                "effective_positions": effective_positions
            },
            "sector_concentration": {
                "max_sector_exposure": max_sector_exposure,
                "sector_breakdown": sector_exposure
            },
            "concentration_score": min(100, (hhi * 100 + top3_concentration * 50)),  # 0-100 scale
            "risk_level": "HIGH" if hhi > 0.25 else "MEDIUM" if hhi > 0.15 else "LOW"
        }

# Utility functions for integration
def create_sample_risk_manager(portfolio_manager=None) -> RiskManager:
    """Create a sample risk manager for testing"""
    risk_manager = RiskManager(portfolio_manager=portfolio_manager)

    # Set some sample risk limits
    risk_manager.update_risk_limits({
        'max_portfolio_var_daily': 0.025,  # 2.5% daily VaR
        'max_position_concentration': 0.15,  # 15% max single position
        'max_drawdown_alert': 0.08,  # 8% drawdown alert
        'max_drawdown_stop': 0.12,  # 12% stop trading
    })

    return risk_manager

class CircuitBreaker:
    """Automatic circuit breaker system for risk management"""

    def __init__(self, portfolio_manager, risk_manager):
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.circuit_breaker_active = False
        self.circuit_breaker_events: List[Dict] = []

        # Circuit breaker thresholds
        self.daily_loss_threshold = 0.05  # 5% daily loss triggers circuit breaker
        self.var_breach_threshold = 0.03  # 3% VaR breach triggers partial closure
        self.critical_drawdown_threshold = 0.15  # 15% drawdown halts all trading
        self.position_size_breach_threshold = 0.25  # 25% single position triggers reduction

    async def monitor_and_trigger(self) -> List[Dict]:
        """
        Monitor portfolio and trigger circuit breakers automatically
        Returns list of actions taken
        """
        actions_taken = []

        if not self.portfolio_manager:
            return actions_taken

        # Get current portfolio state
        portfolio_summary = self.portfolio_manager.get_portfolio_summary()
        current_pnl_pct = portfolio_summary.get('total_pnl_pct', 0)

        # Calculate current risk metrics
        positions_df = self.portfolio_manager.get_positions_df()

        # 1. Check daily loss threshold
        if current_pnl_pct < -self.daily_loss_threshold * 100:
            action = await self._trigger_daily_loss_circuit_breaker(current_pnl_pct)
            if action:
                actions_taken.append(action)

        # 2. Check position size breaches
        if not positions_df.empty:
            for _, position in positions_df.iterrows():
                position_pct = abs(position['market_value']) / portfolio_summary['total_value']
                if position_pct > self.position_size_breach_threshold:
                    action = await self._trigger_position_size_reduction(position, position_pct)
                    if action:
                        actions_taken.append(action)

        # 3. Check critical drawdown
        if current_pnl_pct < -self.critical_drawdown_threshold * 100:
            action = await self._trigger_emergency_halt(current_pnl_pct)
            if action:
                actions_taken.append(action)

        return actions_taken

    async def _trigger_daily_loss_circuit_breaker(self, current_pnl_pct: float) -> Optional[Dict]:
        """Trigger daily loss circuit breaker - reduce all positions by 50%"""
        try:
            positions_df = self.portfolio_manager.get_positions_df()
            if positions_df.empty:
                return None

            positions_closed = []

            for _, position in positions_df.iterrows():
                # Reduce position by 50%
                reduction_quantity = int(position['quantity'] * 0.5)
                if reduction_quantity > 0:
                    # Execute sell order for 50% of position
                    trade = self.portfolio_manager.add_trade(
                        symbol=position['symbol'],
                        quantity=-reduction_quantity,
                        price=position['current_price'],
                        commission=1.0
                    )

                    if trade:
                        positions_closed.append({
                            'symbol': position['symbol'],
                            'quantity_reduced': reduction_quantity,
                            'reason': 'Daily loss circuit breaker'
                        })

            # Log circuit breaker event
            event = {
                'timestamp': datetime.now().isoformat(),
                'type': 'DAILY_LOSS_CIRCUIT_BREAKER',
                'trigger_value': current_pnl_pct,
                'threshold': -self.daily_loss_threshold * 100,
                'action': 'Reduced all positions by 50%',
                'positions_affected': len(positions_closed),
                'details': positions_closed
            }

            self.circuit_breaker_events.append(event)
            logger.critical(f"CIRCUIT BREAKER TRIGGERED: Daily loss {current_pnl_pct:.2f}% exceeded {-self.daily_loss_threshold * 100:.2f}% threshold")

            return event

        except Exception as e:
            logger.error(f"Error triggering daily loss circuit breaker: {e}")
            return None

    async def _trigger_position_size_reduction(self, position: pd.Series, position_pct: float) -> Optional[Dict]:
        """Reduce oversized position to acceptable level"""
        try:
            target_pct = 0.20  # Reduce to 20% of portfolio
            current_value = abs(position['market_value'])
            portfolio_value = self.portfolio_manager.total_value
            target_value = portfolio_value * target_pct

            if current_value <= target_value:
                return None  # Position already within limits

            # Calculate quantity to sell
            value_to_reduce = current_value - target_value
            quantity_to_reduce = int(value_to_reduce / position['current_price'])

            if quantity_to_reduce > 0:
                # Execute sell order
                trade = self.portfolio_manager.add_trade(
                    symbol=position['symbol'],
                    quantity=-quantity_to_reduce,
                    price=position['current_price'],
                    commission=1.0
                )

                if trade:
                    event = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'POSITION_SIZE_CIRCUIT_BREAKER',
                        'symbol': position['symbol'],
                        'trigger_value': position_pct,
                        'threshold': self.position_size_breach_threshold,
                        'action': f'Reduced position by {quantity_to_reduce} shares',
                        'original_value': current_value,
                        'target_value': target_value,
                        'quantity_reduced': quantity_to_reduce
                    }

                    self.circuit_breaker_events.append(event)
                    logger.warning(f"POSITION SIZE CIRCUIT BREAKER: {position['symbol']} reduced from {position_pct:.1%} to {target_pct:.1%}")

                    return event

        except Exception as e:
            logger.error(f"Error triggering position size reduction for {position['symbol']}: {e}")
            return None

    async def _trigger_emergency_halt(self, current_pnl_pct: float) -> Optional[Dict]:
        """Emergency halt - close all positions and halt trading"""
        try:
            positions_df = self.portfolio_manager.get_positions_df()
            if positions_df.empty:
                return None

            positions_closed = []

            # Close ALL positions
            for _, position in positions_df.iterrows():
                if position['quantity'] > 0:
                    # Close entire position
                    trade = self.portfolio_manager.add_trade(
                        symbol=position['symbol'],
                        quantity=-position['quantity'],
                        price=position['current_price'],
                        commission=1.0
                    )

                    if trade:
                        positions_closed.append({
                            'symbol': position['symbol'],
                            'quantity_closed': position['quantity'],
                            'value_closed': position['market_value']
                        })

            # Activate circuit breaker flag
            self.circuit_breaker_active = True

            # Log emergency halt
            event = {
                'timestamp': datetime.now().isoformat(),
                'type': 'EMERGENCY_HALT',
                'trigger_value': current_pnl_pct,
                'threshold': -self.critical_drawdown_threshold * 100,
                'action': 'CLOSED ALL POSITIONS - TRADING HALTED',
                'positions_closed': len(positions_closed),
                'total_value_liquidated': sum([pos['value_closed'] for pos in positions_closed]),
                'details': positions_closed,
                'circuit_breaker_active': True
            }

            self.circuit_breaker_events.append(event)
            logger.critical(f"EMERGENCY HALT TRIGGERED: {current_pnl_pct:.2f}% drawdown exceeded {-self.critical_drawdown_threshold * 100:.2f}% threshold")
            logger.critical("ALL POSITIONS CLOSED - TRADING HALTED")

            return event

        except Exception as e:
            logger.error(f"Error triggering emergency halt: {e}")
            return None

    async def trigger_stop_loss_automation(self, symbol: str, stop_loss_pct: float = 0.05) -> Optional[Dict]:
        """
        Automatic stop-loss trigger for individual positions

        Args:
            symbol: Symbol to check for stop-loss
            stop_loss_pct: Stop-loss percentage (5% default)
        """
        try:
            positions_df = self.portfolio_manager.get_positions_df()

            if positions_df.empty:
                return None

            position_data = positions_df[positions_df['symbol'] == symbol]
            if position_data.empty:
                return None

            position = position_data.iloc[0]

            # Check if position has hit stop-loss
            if position['unrealized_pnl_pct'] <= -stop_loss_pct * 100:
                # Trigger stop-loss - close position
                trade = self.portfolio_manager.add_trade(
                    symbol=symbol,
                    quantity=-position['quantity'],
                    price=position['current_price'],
                    commission=1.0
                )

                if trade:
                    event = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'STOP_LOSS_TRIGGERED',
                        'symbol': symbol,
                        'trigger_value': position['unrealized_pnl_pct'],
                        'threshold': -stop_loss_pct * 100,
                        'action': f'Closed position due to stop-loss',
                        'quantity_closed': position['quantity'],
                        'realized_pnl': position['unrealized_pnl']
                    }

                    self.circuit_breaker_events.append(event)
                    logger.warning(f"STOP-LOSS TRIGGERED: {symbol} closed at {position['unrealized_pnl_pct']:.1f}% loss")

                    return event

        except Exception as e:
            logger.error(f"Error triggering stop-loss for {symbol}: {e}")
            return None

    def reset_circuit_breaker(self) -> bool:
        """Reset circuit breaker after manual review"""
        self.circuit_breaker_active = False

        reset_event = {
            'timestamp': datetime.now().isoformat(),
            'type': 'CIRCUIT_BREAKER_RESET',
            'action': 'Circuit breaker manually reset - trading re-enabled'
        }

        self.circuit_breaker_events.append(reset_event)
        logger.info("Circuit breaker reset - trading re-enabled")

        return True

    def is_trading_halted(self) -> bool:
        """Check if trading is currently halted"""
        return self.circuit_breaker_active

    def get_circuit_breaker_status(self) -> Dict:
        """Get comprehensive circuit breaker status"""
        return {
            'active': self.circuit_breaker_active,
            'events_count': len(self.circuit_breaker_events),
            'recent_events': self.circuit_breaker_events[-5:] if self.circuit_breaker_events else [],
            'thresholds': {
                'daily_loss_threshold': self.daily_loss_threshold,
                'var_breach_threshold': self.var_breach_threshold,
                'critical_drawdown_threshold': self.critical_drawdown_threshold,
                'position_size_breach_threshold': self.position_size_breach_threshold
            }
        }