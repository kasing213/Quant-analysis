"""
Advanced Risk Management System with Enhanced Position Sizing and Stop-Loss
Comprehensive risk management with automated position sizing, dynamic stop-losses, and portfolio protection
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path
import sqlite3
import json

from .risk_manager import (
    RiskManager, RiskAlert, RiskLevel, RiskMetrics,
    PositionSizer, RiskCalculator, CFDRiskManager, CircuitBreaker
)

logger = logging.getLogger(__name__)

class StopLossType(Enum):
    """Types of stop-loss orders"""
    FIXED_PERCENTAGE = "fixed_percentage"
    TRAILING_PERCENTAGE = "trailing_percentage"
    VOLATILITY_BASED = "volatility_based"
    ATR_BASED = "atr_based"
    SUPPORT_RESISTANCE = "support_resistance"
    TIME_BASED = "time_based"

@dataclass
class StopLossOrder:
    """Stop-loss order configuration"""
    symbol: str
    order_type: StopLossType
    trigger_price: float
    quantity: int
    percentage: Optional[float] = None
    trailing_amount: Optional[float] = None
    volatility_multiplier: Optional[float] = None
    atr_period: Optional[int] = None
    atr_multiplier: Optional[float] = None
    expiry_time: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    highest_price: Optional[float] = None  # For trailing stops
    lowest_price: Optional[float] = None

@dataclass
class PositionSizeConfig:
    """Configuration for position sizing"""
    method: str = "kelly"  # kelly, fixed_fractional, volatility_adjusted, risk_parity
    max_position_size: float = 0.20  # Maximum 20% of portfolio per position
    risk_per_trade: float = 0.02  # Risk 2% of capital per trade
    volatility_target: float = 0.15  # Target 15% portfolio volatility
    correlation_threshold: float = 0.7  # Reduce size if correlation > 70%
    concentration_limit: float = 0.25  # Maximum concentration in single asset
    sector_limit: float = 0.40  # Maximum sector concentration
    kelly_cap: float = 0.25  # Cap Kelly sizing at 25%
    min_position_size: float = 0.01  # Minimum 1% position
    rebalance_threshold: float = 0.05  # Rebalance if deviation > 5%

class AdvancedPositionSizer:
    """Advanced position sizing with multiple algorithms"""

    def __init__(self, config: PositionSizeConfig):
        self.config = config

    def calculate_optimal_size(self, symbol: str, account_balance: float,
                             portfolio_data: Dict, market_data: Dict,
                             risk_metrics: RiskMetrics) -> Dict[str, Any]:
        """
        Calculate optimal position size using multiple methods

        Args:
            symbol: Trading symbol
            account_balance: Current account balance
            portfolio_data: Current portfolio positions and weights
            market_data: Market data including volatility, correlations
            risk_metrics: Current portfolio risk metrics

        Returns:
            Dict with recommended position size and rationale
        """

        results = {}

        # 1. Kelly Criterion sizing
        kelly_size = self._kelly_criterion_sizing(symbol, account_balance, market_data)
        results['kelly'] = kelly_size

        # 2. Risk-based sizing
        risk_size = self._risk_based_sizing(symbol, account_balance, market_data)
        results['risk_based'] = risk_size

        # 3. Volatility-adjusted sizing
        vol_size = self._volatility_adjusted_sizing(symbol, account_balance, market_data, risk_metrics)
        results['volatility_adjusted'] = vol_size

        # 4. Correlation-adjusted sizing
        corr_size = self._correlation_adjusted_sizing(symbol, account_balance, portfolio_data, market_data)
        results['correlation_adjusted'] = corr_size

        # 5. Portfolio optimization sizing (risk parity approach)
        opt_size = self._portfolio_optimization_sizing(symbol, account_balance, portfolio_data, market_data)
        results['portfolio_optimized'] = opt_size

        # 6. Combine methods based on configuration
        final_size = self._combine_sizing_methods(results, symbol, account_balance)

        return {
            'recommended_size_dollars': final_size,
            'recommended_size_pct': final_size / account_balance,
            'methodology_breakdown': results,
            'risk_constraints_applied': self._get_applied_constraints(symbol, portfolio_data),
            'sizing_rationale': self._generate_sizing_rationale(results, final_size, account_balance)
        }

    def _kelly_criterion_sizing(self, symbol: str, account_balance: float, market_data: Dict) -> float:
        """Enhanced Kelly Criterion with safeguards"""

        # Get historical performance data (would come from backtesting or live trading history)
        win_rate = market_data.get('historical_win_rate', 0.55)
        avg_win = market_data.get('avg_win_pct', 0.03)
        avg_loss = market_data.get('avg_loss_pct', 0.02)

        if avg_loss <= 0 or avg_win <= 0:
            return account_balance * self.config.min_position_size

        # Standard Kelly formula
        win_loss_ratio = avg_win / avg_loss
        kelly_fraction = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Apply Kelly cap to prevent over-leverage
        kelly_fraction = max(0.0, min(kelly_fraction, self.config.kelly_cap))

        # Apply maximum position size constraint
        kelly_fraction = min(kelly_fraction, self.config.max_position_size)

        return account_balance * kelly_fraction

    def _risk_based_sizing(self, symbol: str, account_balance: float, market_data: Dict) -> float:
        """Size position based on fixed risk per trade"""

        # Calculate position size based on stop-loss distance
        current_price = market_data.get('current_price', 100)
        volatility = market_data.get('volatility', 0.02)  # Daily volatility

        # Use 2x daily volatility as stop-loss distance (approximately 95% confidence)
        stop_loss_distance_pct = volatility * 2

        # Risk amount we're willing to lose
        risk_amount = account_balance * self.config.risk_per_trade

        # Position size = Risk Amount / Stop Loss Distance
        position_value = risk_amount / stop_loss_distance_pct

        # Cap at maximum position size
        max_position_value = account_balance * self.config.max_position_size
        position_value = min(position_value, max_position_value)

        return position_value

    def _volatility_adjusted_sizing(self, symbol: str, account_balance: float,
                                  market_data: Dict, risk_metrics: RiskMetrics) -> float:
        """Adjust position size based on volatility targeting"""

        symbol_volatility = market_data.get('volatility', 0.02) * np.sqrt(252)  # Annualized
        portfolio_volatility = risk_metrics.volatility_annualized or 0.15

        # Calculate volatility scalar
        vol_scalar = self.config.volatility_target / symbol_volatility

        # Base allocation adjusted for volatility
        base_allocation = self.config.max_position_size * 0.5  # Start with 50% of max
        adjusted_allocation = base_allocation * vol_scalar

        # Apply bounds
        adjusted_allocation = max(self.config.min_position_size,
                                min(adjusted_allocation, self.config.max_position_size))

        return account_balance * adjusted_allocation

    def _correlation_adjusted_sizing(self, symbol: str, account_balance: float,
                                   portfolio_data: Dict, market_data: Dict) -> float:
        """Adjust size based on correlation with existing positions"""

        base_size = account_balance * self.config.max_position_size

        # Get correlations with existing positions
        correlations = market_data.get('correlations', {})
        existing_positions = portfolio_data.get('positions', {})

        if not correlations or not existing_positions:
            return base_size

        # Calculate correlation penalty
        max_correlation = 0
        weighted_correlation = 0
        total_weight = 0

        for existing_symbol, position_data in existing_positions.items():
            if existing_symbol == symbol:
                continue

            correlation = correlations.get(existing_symbol, 0)
            position_weight = position_data.get('weight', 0)

            max_correlation = max(max_correlation, abs(correlation))
            weighted_correlation += abs(correlation) * position_weight
            total_weight += position_weight

        if total_weight > 0:
            weighted_correlation /= total_weight

        # Apply correlation penalty
        if max_correlation > self.config.correlation_threshold:
            correlation_penalty = (max_correlation - self.config.correlation_threshold) / (1 - self.config.correlation_threshold)
            size_reduction = correlation_penalty * 0.5  # Reduce by up to 50%
            base_size *= (1 - size_reduction)

        return base_size

    def _portfolio_optimization_sizing(self, symbol: str, account_balance: float,
                                     portfolio_data: Dict, market_data: Dict) -> float:
        """Use risk parity / portfolio optimization approach"""

        # Simplified risk parity: size inversely proportional to volatility
        symbol_volatility = market_data.get('volatility', 0.02) * np.sqrt(252)

        # Get volatilities of existing positions
        existing_positions = portfolio_data.get('positions', {})
        volatilities = {symbol: symbol_volatility}

        for pos_symbol, pos_data in existing_positions.items():
            pos_vol = pos_data.get('volatility', 0.15)
            volatilities[pos_symbol] = pos_vol

        # Calculate risk parity weights
        inv_vol_weights = {s: 1/vol for s, vol in volatilities.items()}
        total_inv_vol = sum(inv_vol_weights.values())

        # Normalize weights
        risk_parity_weight = inv_vol_weights[symbol] / total_inv_vol

        # Apply constraints
        risk_parity_weight = min(risk_parity_weight, self.config.max_position_size)
        risk_parity_weight = max(risk_parity_weight, self.config.min_position_size)

        return account_balance * risk_parity_weight

    def _combine_sizing_methods(self, results: Dict, symbol: str, account_balance: float) -> float:
        """Combine different sizing methods based on configuration"""

        method = self.config.method.lower()

        if method == "kelly":
            return results['kelly']
        elif method == "risk_based":
            return results['risk_based']
        elif method == "volatility_adjusted":
            return results['volatility_adjusted']
        elif method == "correlation_adjusted":
            return results['correlation_adjusted']
        elif method == "portfolio_optimized":
            return results['portfolio_optimized']
        elif method == "ensemble":
            # Weighted average of all methods
            weights = {
                'kelly': 0.25,
                'risk_based': 0.25,
                'volatility_adjusted': 0.20,
                'correlation_adjusted': 0.15,
                'portfolio_optimized': 0.15
            }

            weighted_sum = sum(results[method] * weight for method, weight in weights.items())
            return weighted_sum
        else:
            # Default to risk-based
            return results['risk_based']

    def _get_applied_constraints(self, symbol: str, portfolio_data: Dict) -> List[str]:
        """Track which constraints were applied"""
        constraints = []

        existing_positions = portfolio_data.get('positions', {})

        # Check concentration limits
        if len(existing_positions) > 0:
            constraints.append("correlation_adjustment")

        constraints.extend([
            "max_position_limit",
            "min_position_limit",
            "risk_per_trade_limit"
        ])

        return constraints

    def _generate_sizing_rationale(self, results: Dict, final_size: float, account_balance: float) -> str:
        """Generate human-readable rationale for sizing decision"""

        final_pct = (final_size / account_balance) * 100

        rationale = f"Recommended position size: {final_pct:.1f}% of portfolio (${final_size:,.0f}). "

        # Compare methods
        method_sizes = {k: v/account_balance*100 for k, v in results.items()}

        min_method = min(method_sizes, key=method_sizes.get)
        max_method = max(method_sizes, key=method_sizes.get)

        rationale += f"Range: {method_sizes[min_method]:.1f}% ({min_method}) to {method_sizes[max_method]:.1f}% ({max_method}). "

        if final_pct < 5:
            rationale += "Conservative sizing due to high risk or correlation."
        elif final_pct > 15:
            rationale += "Aggressive sizing based on favorable risk-reward."
        else:
            rationale += "Moderate sizing balancing risk and opportunity."

        return rationale

class DynamicStopLossManager:
    """Advanced stop-loss management with multiple strategies"""

    def __init__(self, portfolio_manager, db_path: str = "stop_losses.db"):
        self.portfolio_manager = portfolio_manager
        self.db_path = Path(db_path)
        self.active_stops: Dict[str, StopLossOrder] = {}
        self._init_database()

    def _init_database(self):
        """Initialize stop-loss database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stop_loss_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    trigger_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    percentage REAL,
                    trailing_amount REAL,
                    volatility_multiplier REAL,
                    atr_period INTEGER,
                    atr_multiplier REAL,
                    expiry_time TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    highest_price REAL,
                    lowest_price REAL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS stop_loss_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    trigger_price REAL NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    realized_pnl REAL,
                    trigger_reason TEXT
                )
            ''')

    def create_stop_loss(self, symbol: str, stop_type: StopLossType,
                        quantity: int, **kwargs) -> StopLossOrder:
        """Create a new stop-loss order"""

        current_price = kwargs.get('current_price', 100.0)

        if stop_type == StopLossType.FIXED_PERCENTAGE:
            percentage = kwargs.get('percentage', 0.05)  # 5% default
            trigger_price = current_price * (1 - percentage) if quantity > 0 else current_price * (1 + percentage)

        elif stop_type == StopLossType.TRAILING_PERCENTAGE:
            percentage = kwargs.get('percentage', 0.05)
            trailing_amount = current_price * percentage
            trigger_price = current_price - trailing_amount if quantity > 0 else current_price + trailing_amount

        elif stop_type == StopLossType.VOLATILITY_BASED:
            volatility = kwargs.get('volatility', 0.02)
            multiplier = kwargs.get('volatility_multiplier', 2.0)
            stop_distance = volatility * multiplier * current_price
            trigger_price = current_price - stop_distance if quantity > 0 else current_price + stop_distance

        elif stop_type == StopLossType.ATR_BASED:
            atr_value = kwargs.get('atr_value', current_price * 0.02)
            multiplier = kwargs.get('atr_multiplier', 2.0)
            stop_distance = atr_value * multiplier
            trigger_price = current_price - stop_distance if quantity > 0 else current_price + stop_distance

        else:
            trigger_price = kwargs.get('trigger_price', current_price * 0.95)

        stop_order = StopLossOrder(
            symbol=symbol,
            order_type=stop_type,
            trigger_price=trigger_price,
            quantity=quantity,
            percentage=kwargs.get('percentage'),
            trailing_amount=kwargs.get('trailing_amount'),
            volatility_multiplier=kwargs.get('volatility_multiplier'),
            atr_period=kwargs.get('atr_period'),
            atr_multiplier=kwargs.get('atr_multiplier'),
            expiry_time=kwargs.get('expiry_time'),
            highest_price=current_price if quantity > 0 else None,
            lowest_price=current_price if quantity < 0 else None
        )

        self.active_stops[symbol] = stop_order
        self._save_stop_loss(stop_order)

        logger.info(f"Created {stop_type.value} stop-loss for {symbol} at ${trigger_price:.2f}")
        return stop_order

    def update_stop_losses(self, market_data: Dict[str, Dict]) -> List[Dict]:
        """Update all active stop-losses and check for triggers"""

        triggered_stops = []

        for symbol, stop_order in list(self.active_stops.items()):
            if not stop_order.is_active:
                continue

            current_price = market_data.get(symbol, {}).get('current_price')
            if not current_price:
                continue

            # Check for expiry
            if stop_order.expiry_time and datetime.now() > stop_order.expiry_time:
                self._deactivate_stop_loss(symbol, "Expired")
                continue

            # Update trailing stops
            if stop_order.order_type == StopLossType.TRAILING_PERCENTAGE:
                self._update_trailing_stop(stop_order, current_price)

            # Check for trigger
            triggered = self._check_stop_trigger(stop_order, current_price)
            if triggered:
                trigger_info = self._execute_stop_loss(stop_order, current_price)
                if trigger_info:
                    triggered_stops.append(trigger_info)

        return triggered_stops

    def _update_trailing_stop(self, stop_order: StopLossOrder, current_price: float):
        """Update trailing stop-loss levels"""

        updated = False

        if stop_order.quantity > 0:  # Long position
            if stop_order.highest_price is None or current_price > stop_order.highest_price:
                stop_order.highest_price = current_price

                if stop_order.trailing_amount:
                    new_trigger = current_price - stop_order.trailing_amount
                    if new_trigger > stop_order.trigger_price:
                        stop_order.trigger_price = new_trigger
                        updated = True

        else:  # Short position
            if stop_order.lowest_price is None or current_price < stop_order.lowest_price:
                stop_order.lowest_price = current_price

                if stop_order.trailing_amount:
                    new_trigger = current_price + stop_order.trailing_amount
                    if new_trigger < stop_order.trigger_price:
                        stop_order.trigger_price = new_trigger
                        updated = True

        if updated:
            stop_order.last_updated = datetime.now()
            self._save_stop_loss(stop_order)
            logger.debug(f"Updated trailing stop for {stop_order.symbol} to ${stop_order.trigger_price:.2f}")

    def _check_stop_trigger(self, stop_order: StopLossOrder, current_price: float) -> bool:
        """Check if stop-loss should be triggered"""

        if stop_order.quantity > 0:  # Long position
            return current_price <= stop_order.trigger_price
        else:  # Short position
            return current_price >= stop_order.trigger_price

    def _execute_stop_loss(self, stop_order: StopLossOrder, trigger_price: float) -> Optional[Dict]:
        """Execute stop-loss order"""

        try:
            # Get current position
            positions_df = self.portfolio_manager.get_positions_df()
            position_data = positions_df[positions_df['symbol'] == stop_order.symbol]

            if position_data.empty:
                logger.warning(f"No position found for stop-loss {stop_order.symbol}")
                return None

            position = position_data.iloc[0]

            # Execute the trade (close position)
            trade = self.portfolio_manager.add_trade(
                symbol=stop_order.symbol,
                quantity=-stop_order.quantity,  # Opposite of position
                price=trigger_price,
                commission=1.0
            )

            if trade:
                # Calculate realized P&L
                avg_cost = position['avg_cost']
                realized_pnl = (trigger_price - avg_cost) * abs(stop_order.quantity)
                if stop_order.quantity < 0:  # Short position
                    realized_pnl = -realized_pnl

                # Log trigger
                trigger_info = {
                    'symbol': stop_order.symbol,
                    'trigger_time': datetime.now().isoformat(),
                    'trigger_price': trigger_price,
                    'order_type': stop_order.order_type.value,
                    'quantity': stop_order.quantity,
                    'realized_pnl': realized_pnl,
                    'trigger_reason': 'Price breach'
                }

                self._log_stop_trigger(trigger_info)
                self._deactivate_stop_loss(stop_order.symbol, "Triggered")

                logger.info(f"STOP-LOSS TRIGGERED: {stop_order.symbol} at ${trigger_price:.2f}, P&L: ${realized_pnl:.2f}")

                return trigger_info

        except Exception as e:
            logger.error(f"Error executing stop-loss for {stop_order.symbol}: {e}")

        return None

    def _save_stop_loss(self, stop_order: StopLossOrder):
        """Save stop-loss order to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO stop_loss_orders
                (symbol, order_type, trigger_price, quantity, percentage, trailing_amount,
                 volatility_multiplier, atr_period, atr_multiplier, expiry_time, is_active,
                 created_at, last_updated, highest_price, lowest_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stop_order.symbol,
                stop_order.order_type.value,
                stop_order.trigger_price,
                stop_order.quantity,
                stop_order.percentage,
                stop_order.trailing_amount,
                stop_order.volatility_multiplier,
                stop_order.atr_period,
                stop_order.atr_multiplier,
                stop_order.expiry_time.isoformat() if stop_order.expiry_time else None,
                stop_order.is_active,
                stop_order.created_at.isoformat(),
                stop_order.last_updated.isoformat(),
                stop_order.highest_price,
                stop_order.lowest_price
            ))

    def _log_stop_trigger(self, trigger_info: Dict):
        """Log stop-loss trigger to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO stop_loss_triggers
                (symbol, trigger_time, trigger_price, order_type, quantity, realized_pnl, trigger_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                trigger_info['symbol'],
                trigger_info['trigger_time'],
                trigger_info['trigger_price'],
                trigger_info['order_type'],
                trigger_info['quantity'],
                trigger_info['realized_pnl'],
                trigger_info['trigger_reason']
            ))

    def _deactivate_stop_loss(self, symbol: str, reason: str):
        """Deactivate a stop-loss order"""
        if symbol in self.active_stops:
            self.active_stops[symbol].is_active = False
            logger.info(f"Deactivated stop-loss for {symbol}: {reason}")
            del self.active_stops[symbol]

    def get_active_stops(self) -> Dict[str, StopLossOrder]:
        """Get all active stop-loss orders"""
        return {k: v for k, v in self.active_stops.items() if v.is_active}

    def get_stop_loss_performance(self) -> Dict[str, Any]:
        """Analyze stop-loss performance"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('''
                SELECT * FROM stop_loss_triggers
                ORDER BY trigger_time DESC
            ''', conn)

        if df.empty:
            return {"total_triggers": 0}

        return {
            "total_triggers": len(df),
            "total_realized_pnl": df['realized_pnl'].sum(),
            "avg_realized_pnl": df['realized_pnl'].mean(),
            "profitable_stops": len(df[df['realized_pnl'] > 0]),
            "loss_prevention": abs(df[df['realized_pnl'] < 0]['realized_pnl'].sum()),
            "most_recent_triggers": df.head(5).to_dict('records')
        }

class EnhancedRiskManager(RiskManager):
    """Enhanced risk manager with advanced position sizing and stop-losses"""

    def __init__(self, portfolio_manager=None, db_path: str = "enhanced_risk.db"):
        super().__init__(portfolio_manager, db_path)

        # Enhanced components
        self.position_sizer = AdvancedPositionSizer(PositionSizeConfig())
        self.stop_loss_manager = DynamicStopLossManager(portfolio_manager)
        self.circuit_breaker = CircuitBreaker(portfolio_manager, self) if portfolio_manager else None

        # Enhanced risk limits
        self.enhanced_limits = {
            'max_leverage_ratio': 3.0,
            'max_sector_beta': 1.5,
            'min_diversification_ratio': 0.7,
            'max_tail_risk': 0.08,
            'max_skewness': -0.5,
            'min_liquidity_coverage': 0.15
        }

        self.risk_limits.update(self.enhanced_limits)

    def calculate_position_size_advanced(self, symbol: str, signal_strength: float = 1.0,
                                       market_regime: str = "normal") -> Dict[str, Any]:
        """
        Advanced position sizing with signal strength and market regime adjustment

        Args:
            symbol: Trading symbol
            signal_strength: Signal confidence (0-1)
            market_regime: Market regime ("bull", "bear", "sideways", "volatile")
        """

        if not self.portfolio_manager:
            return {"error": "No portfolio manager available"}

        account_balance = self.portfolio_manager.total_value

        # Get current portfolio data
        positions_df = self.portfolio_manager.get_positions_df()
        portfolio_data = {
            'positions': {
                row['symbol']: {
                    'weight': abs(row['market_value']) / account_balance,
                    'volatility': 0.15  # Placeholder - would get from market data
                }
                for _, row in positions_df.iterrows()
            }
        }

        # Mock market data (in production, this would come from data feeds)
        market_data = {
            'current_price': 100.0,
            'volatility': 0.02,  # Daily volatility
            'historical_win_rate': 0.58,
            'avg_win_pct': 0.04,
            'avg_loss_pct': 0.025,
            'correlations': {}  # Would contain correlations with existing positions
        }

        # Calculate base position size
        sizing_result = self.position_sizer.calculate_optimal_size(
            symbol, account_balance, portfolio_data, market_data, self.calculate_portfolio_risk_metrics()
        )

        # Adjust for signal strength
        signal_adjustment = 0.5 + (signal_strength * 0.5)  # Scale from 0.5 to 1.0
        sizing_result['recommended_size_dollars'] *= signal_adjustment

        # Adjust for market regime
        regime_adjustments = {
            "bull": 1.1,      # Slightly more aggressive in bull markets
            "bear": 0.7,      # More conservative in bear markets
            "sideways": 0.9,  # Slightly conservative in sideways markets
            "volatile": 0.6   # Much more conservative in volatile markets
        }

        regime_factor = regime_adjustments.get(market_regime, 1.0)
        sizing_result['recommended_size_dollars'] *= regime_factor

        # Recalculate percentage
        sizing_result['recommended_size_pct'] = sizing_result['recommended_size_dollars'] / account_balance

        # Add adjustment details
        sizing_result['adjustments'] = {
            'signal_strength': signal_strength,
            'signal_adjustment': signal_adjustment,
            'market_regime': market_regime,
            'regime_adjustment': regime_factor,
            'final_adjustment': signal_adjustment * regime_factor
        }

        return sizing_result

    def create_comprehensive_stop_loss(self, symbol: str, quantity: int,
                                     stop_type: str = "trailing", **kwargs) -> Dict:
        """Create comprehensive stop-loss with multiple fallbacks"""

        try:
            # Parse stop type
            if stop_type == "trailing":
                stop_loss_type = StopLossType.TRAILING_PERCENTAGE
                kwargs.setdefault('percentage', 0.05)  # 5% trailing
            elif stop_type == "volatility":
                stop_loss_type = StopLossType.VOLATILITY_BASED
                kwargs.setdefault('volatility_multiplier', 2.0)
            elif stop_type == "atr":
                stop_loss_type = StopLossType.ATR_BASED
                kwargs.setdefault('atr_multiplier', 2.0)
            else:
                stop_loss_type = StopLossType.FIXED_PERCENTAGE
                kwargs.setdefault('percentage', 0.05)

            # Create primary stop-loss
            primary_stop = self.stop_loss_manager.create_stop_loss(
                symbol, stop_loss_type, quantity, **kwargs
            )

            # Create backup time-based stop (for stale positions)
            backup_kwargs = kwargs.copy()
            backup_kwargs['expiry_time'] = datetime.now() + timedelta(days=30)  # 30-day max hold

            backup_stop = self.stop_loss_manager.create_stop_loss(
                symbol, StopLossType.TIME_BASED, quantity, **backup_kwargs
            )

            return {
                'primary_stop': primary_stop,
                'backup_stop': backup_stop,
                'status': 'active',
                'creation_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating comprehensive stop-loss for {symbol}: {e}")
            return {'error': str(e)}

    async def monitor_portfolio_risk(self) -> Dict[str, Any]:
        """Comprehensive real-time portfolio risk monitoring"""

        monitoring_results = {
            'timestamp': datetime.now().isoformat(),
            'risk_level': 'GREEN',
            'alerts': [],
            'circuit_breaker_status': None,
            'stop_loss_status': None,
            'recommendations': []
        }

        try:
            # 1. Update stop-losses
            if self.stop_loss_manager and self.portfolio_manager:
                positions_df = self.portfolio_manager.get_positions_df()
                market_data = {}

                # Mock current prices (would come from real data feed)
                for _, pos in positions_df.iterrows():
                    market_data[pos['symbol']] = {
                        'current_price': pos['current_price']
                    }

                triggered_stops = self.stop_loss_manager.update_stop_losses(market_data)
                monitoring_results['stop_loss_status'] = {
                    'active_stops': len(self.stop_loss_manager.get_active_stops()),
                    'triggered_this_cycle': len(triggered_stops),
                    'recent_triggers': triggered_stops
                }

            # 2. Check circuit breakers
            if self.circuit_breaker:
                circuit_actions = await self.circuit_breaker.monitor_and_trigger()
                monitoring_results['circuit_breaker_status'] = {
                    'is_active': self.circuit_breaker.is_trading_halted(),
                    'actions_taken': len(circuit_actions),
                    'recent_actions': circuit_actions
                }

                if circuit_actions:
                    monitoring_results['risk_level'] = 'RED'

            # 3. Calculate current risk metrics
            risk_metrics = self.calculate_portfolio_risk_metrics()

            # 4. Check risk limits
            alerts = self.check_risk_limits(risk_metrics)
            monitoring_results['alerts'] = [
                {
                    'type': alert.risk_type,
                    'level': alert.level.value,
                    'message': alert.message,
                    'action': alert.recommended_action
                }
                for alert in alerts
            ]

            # Determine overall risk level
            if any(alert.level == RiskLevel.CRITICAL for alert in alerts):
                monitoring_results['risk_level'] = 'RED'
            elif any(alert.level == RiskLevel.HIGH for alert in alerts):
                monitoring_results['risk_level'] = 'YELLOW'

            # 5. Generate recommendations
            recommendations = self._generate_risk_recommendations(risk_metrics, alerts)
            monitoring_results['recommendations'] = recommendations

        except Exception as e:
            logger.error(f"Error in portfolio risk monitoring: {e}")
            monitoring_results['error'] = str(e)
            monitoring_results['risk_level'] = 'UNKNOWN'

        return monitoring_results

    def _generate_risk_recommendations(self, risk_metrics: RiskMetrics,
                                     alerts: List[RiskAlert]) -> List[str]:
        """Generate actionable risk management recommendations"""

        recommendations = []

        # Concentration risk recommendations
        if risk_metrics.concentration_risk and risk_metrics.concentration_risk > 0.15:
            recommendations.append(
                f"Consider reducing largest position (currently {risk_metrics.concentration_risk:.1%}). "
                f"Target maximum single position of 15%."
            )

        # Volatility recommendations
        if risk_metrics.volatility_annualized and risk_metrics.volatility_annualized > 0.25:
            recommendations.append(
                f"Portfolio volatility is high ({risk_metrics.volatility_annualized:.1%}). "
                f"Consider reducing position sizes or adding defensive assets."
            )

        # Sharpe ratio recommendations
        if risk_metrics.sharpe_ratio and risk_metrics.sharpe_ratio < 0.5:
            recommendations.append(
                f"Risk-adjusted returns are low (Sharpe: {risk_metrics.sharpe_ratio:.2f}). "
                f"Review strategy performance and consider adjustments."
            )

        # Drawdown recommendations
        if risk_metrics.current_drawdown and risk_metrics.current_drawdown > 0.05:
            recommendations.append(
                f"Current drawdown is {risk_metrics.current_drawdown:.1%}. "
                f"Consider defensive positioning or reducing exposure."
            )

        # Alert-based recommendations
        for alert in alerts:
            if alert.recommended_action:
                recommendations.append(alert.recommended_action)

        # Default recommendations if portfolio is healthy
        if not recommendations:
            recommendations.append("Portfolio risk metrics are within acceptable ranges. Continue monitoring.")

            if risk_metrics.concentration_risk and risk_metrics.concentration_risk < 0.10:
                recommendations.append("Good diversification. Consider gradual position increases if opportunities arise.")

        return recommendations[:5]  # Limit to top 5 recommendations

    def get_enhanced_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive enhanced risk report"""

        base_report = self.get_risk_report()

        enhanced_report = {
            **base_report,
            'enhanced_features': {
                'position_sizing': {
                    'methodology': self.position_sizer.config.method,
                    'risk_per_trade': self.position_sizer.config.risk_per_trade,
                    'max_position_size': self.position_sizer.config.max_position_size,
                    'volatility_target': self.position_sizer.config.volatility_target
                },
                'stop_loss_management': self.stop_loss_manager.get_stop_loss_performance(),
                'circuit_breaker': self.circuit_breaker.get_circuit_breaker_status() if self.circuit_breaker else None
            },
            'risk_scoring': self._calculate_risk_score(),
            'optimization_suggestions': self._get_optimization_suggestions()
        }

        return enhanced_report

    def _calculate_risk_score(self) -> Dict[str, Any]:
        """Calculate overall portfolio risk score (0-100)"""

        risk_metrics = self.calculate_portfolio_risk_metrics()

        scores = {}

        # Concentration score (lower is better)
        if risk_metrics.concentration_risk:
            conc_score = max(0, 100 - (risk_metrics.concentration_risk * 500))  # 20% = 0 points
            scores['concentration'] = conc_score

        # Volatility score
        if risk_metrics.volatility_annualized:
            vol_score = max(0, 100 - ((risk_metrics.volatility_annualized - 0.10) * 500))  # >30% = 0 points
            scores['volatility'] = vol_score

        # Sharpe score
        if risk_metrics.sharpe_ratio:
            sharpe_score = min(100, max(0, risk_metrics.sharpe_ratio * 50))  # 2.0 Sharpe = 100 points
            scores['sharpe'] = sharpe_score

        # Drawdown score
        if risk_metrics.current_drawdown:
            dd_score = max(0, 100 - (risk_metrics.current_drawdown * 1000))  # 10% DD = 0 points
            scores['drawdown'] = dd_score

        # Overall score (weighted average)
        if scores:
            weights = {'concentration': 0.25, 'volatility': 0.25, 'sharpe': 0.30, 'drawdown': 0.20}
            overall_score = sum(scores.get(metric, 50) * weight for metric, weight in weights.items())
        else:
            overall_score = 50  # Neutral score if no data

        return {
            'overall_score': round(overall_score, 1),
            'component_scores': scores,
            'rating': 'EXCELLENT' if overall_score >= 80 else
                     'GOOD' if overall_score >= 60 else
                     'FAIR' if overall_score >= 40 else
                     'POOR'
        }

    def _get_optimization_suggestions(self) -> List[str]:
        """Get portfolio optimization suggestions"""

        suggestions = []

        risk_score = self._calculate_risk_score()

        if risk_score['overall_score'] < 60:
            suggestions.append("Overall risk management needs improvement. Focus on the lowest-scoring areas.")

        if 'concentration' in risk_score['component_scores'] and risk_score['component_scores']['concentration'] < 70:
            suggestions.append("Reduce position concentration by diversifying across more assets or sectors.")

        if 'volatility' in risk_score['component_scores'] and risk_score['component_scores']['volatility'] < 70:
            suggestions.append("Consider volatility targeting to reduce portfolio volatility.")

        if 'sharpe' in risk_score['component_scores'] and risk_score['component_scores']['sharpe'] < 50:
            suggestions.append("Focus on risk-adjusted returns. Consider strategy refinement or alpha generation.")

        # Stop-loss suggestions
        active_stops = self.stop_loss_manager.get_active_stops()
        total_positions = len(self.portfolio_manager.get_positions_df()) if self.portfolio_manager else 0

        if total_positions > 0 and len(active_stops) < total_positions * 0.8:
            suggestions.append("Consider implementing stop-losses for more positions to limit downside risk.")

        return suggestions[:3]  # Top 3 suggestions

# Factory function for easy integration
def create_enhanced_risk_manager(portfolio_manager) -> EnhancedRiskManager:
    """Create enhanced risk manager with default configuration"""

    risk_manager = EnhancedRiskManager(portfolio_manager)

    # Set production-ready risk limits
    risk_manager.update_risk_limits({
        'max_portfolio_var_daily': 0.02,     # 2% daily VaR limit
        'max_position_concentration': 0.15,   # 15% max single position
        'max_sector_concentration': 0.30,     # 30% max sector exposure
        'max_drawdown_alert': 0.08,          # 8% drawdown warning
        'max_drawdown_stop': 0.12,           # 12% emergency stop
        'min_sharpe_ratio': 0.75,            # Minimum Sharpe ratio
        'max_leverage_ratio': 2.5,           # Maximum portfolio leverage
        'min_liquidity_coverage': 0.10       # 10% minimum cash
    })

    return risk_manager