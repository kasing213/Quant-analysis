"""
Portfolio Management System
Handles position tracking, P&L calculation, and portfolio analytics with IB integration
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import sqlite3
from pathlib import Path
import asyncio

from .ib_client import create_ib_client
from .data_manager import DataManager

logger = logging.getLogger(__name__)

class Position:
    """Individual position tracking"""
    def __init__(self, symbol: str, quantity: int, avg_price: float,
                 entry_date: datetime = None, position_id: str = None):
        self.symbol = symbol
        self.quantity = quantity  # Positive for long, negative for short
        self.avg_price = avg_price
        self.entry_date = entry_date or datetime.now()
        self.position_id = position_id or f"{symbol}_{int(datetime.now().timestamp())}"
        self.current_price = avg_price
        self.last_updated = datetime.now()

    @property
    def market_value(self) -> float:
        """Current market value of position"""
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss"""
        return self.quantity * (self.current_price - self.avg_price)

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage"""
        if self.avg_price == 0:
            return 0
        return (self.current_price / self.avg_price - 1) * 100

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    def update_price(self, new_price: float):
        """Update current price"""
        self.current_price = new_price
        self.last_updated = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/display"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'entry_date': self.entry_date.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'side': 'LONG' if self.is_long else 'SHORT'
        }

class Trade:
    """Individual trade record"""
    def __init__(self, symbol: str, quantity: int, price: float, side: str,
                 trade_date: datetime = None, trade_id: str = None,
                 commission: float = 0, position_id: str = None):
        self.symbol = symbol
        self.quantity = abs(quantity)  # Always positive
        self.price = price
        self.side = side.upper()  # 'BUY' or 'SELL'
        self.trade_date = trade_date or datetime.now()
        self.trade_id = trade_id or f"{symbol}_{int(datetime.now().timestamp())}"
        self.commission = commission
        self.position_id = position_id

    @property
    def trade_value(self) -> float:
        """Gross value of trade"""
        return self.quantity * self.price

    @property
    def net_value(self) -> float:
        """Net value after commission"""
        return self.trade_value - self.commission

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/display"""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'side': self.side,
            'trade_value': self.trade_value,
            'commission': self.commission,
            'net_value': self.net_value,
            'trade_date': self.trade_date.isoformat(),
            'position_id': self.position_id
        }

class PortfolioManager:
    """Main portfolio management class"""

    def __init__(self, initial_cash: float = 100000, db_path: str = "portfolio.db",
                 use_ib: bool = True, paper_trading: bool = True):
        self.initial_cash = initial_cash
        self.cash_balance = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.db_path = Path(db_path)
        self.use_ib = use_ib
        self.paper_trading = paper_trading
        self.data_manager = DataManager(use_ib_for_data=False, use_ib_for_trading=use_ib, paper_trading=paper_trading)

        # Risk management parameters
        self.max_position_size_pct = 20.0  # Max 20% of portfolio in single position
        self.max_sector_exposure_pct = 40.0  # Max 40% exposure to single sector
        self.max_daily_loss_pct = 5.0  # Max 5% daily loss
        self.max_portfolio_leverage = 1.0  # No leverage for conservative trading
        self.min_cash_reserve_pct = 10.0  # Keep 10% cash reserve

        # Risk tracking
        self.daily_start_value = initial_cash
        self.rejected_orders: List[Dict] = []

        # Initialize database
        self._init_database()
        self._load_portfolio()

    def _init_database(self):
        """Initialize SQLite database for portfolio tracking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    entry_date TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    side TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    commission REAL DEFAULT 0,
                    position_id TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS account_info (
                    id INTEGER PRIMARY KEY,
                    cash_balance REAL NOT NULL,
                    last_updated TEXT NOT NULL
                )
            ''')

    def _load_portfolio(self):
        """Load portfolio from database"""
        with sqlite3.connect(self.db_path) as conn:
            # Load positions
            pos_df = pd.read_sql_query('SELECT * FROM positions', conn)
            for _, row in pos_df.iterrows():
                position = Position(
                    symbol=row['symbol'],
                    quantity=row['quantity'],
                    avg_price=row['avg_price'],
                    entry_date=datetime.fromisoformat(row['entry_date']),
                    position_id=row['position_id']
                )
                self.positions[row['symbol']] = position

            # Load trades
            trades_df = pd.read_sql_query('SELECT * FROM trades', conn)
            for _, row in trades_df.iterrows():
                trade = Trade(
                    symbol=row['symbol'],
                    quantity=row['quantity'],
                    price=row['price'],
                    side=row['side'],
                    trade_date=datetime.fromisoformat(row['trade_date']),
                    trade_id=row['trade_id'],
                    commission=row['commission'],
                    position_id=row.get('position_id')
                )
                self.trades.append(trade)

            # Load cash balance
            cash_df = pd.read_sql_query('SELECT * FROM account_info ORDER BY last_updated DESC LIMIT 1', conn)
            if not cash_df.empty:
                self.cash_balance = cash_df.iloc[0]['cash_balance']

    def validate_order(self, symbol: str, quantity: int, price: float, commission: float = 1.0) -> Dict:
        """
        Comprehensive pre-trade risk validation
        Returns: {'valid': bool, 'reason': str, 'risk_metrics': dict}
        """
        side = "BUY" if quantity > 0 else "SELL"
        abs_quantity = abs(quantity)
        order_value = abs_quantity * price

        validation_result = {
            'valid': True,
            'reason': '',
            'risk_metrics': {},
            'order_details': {
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'side': side,
                'order_value': order_value,
                'commission': commission
            }
        }

        # 1. Basic liquidity checks
        if side == "BUY":
            total_cost = order_value + commission
            if total_cost > self.cash_balance:
                validation_result.update({
                    'valid': False,
                    'reason': f'Insufficient cash: Need ${total_cost:.2f}, have ${self.cash_balance:.2f}'
                })
                return validation_result

        if side == "SELL":
            current_position = self.positions.get(symbol)
            available_shares = current_position.quantity if current_position else 0
            if abs_quantity > available_shares:
                validation_result.update({
                    'valid': False,
                    'reason': f'Insufficient shares: Need {abs_quantity}, have {available_shares}'
                })
                return validation_result

        # 2. Position size limits
        if side == "BUY":
            current_position_value = 0
            if symbol in self.positions:
                current_position_value = self.positions[symbol].market_value

            new_position_value = current_position_value + order_value
            position_pct = (new_position_value / self.total_value) * 100

            if position_pct > self.max_position_size_pct:
                validation_result.update({
                    'valid': False,
                    'reason': f'Position size limit exceeded: {position_pct:.1f}% > {self.max_position_size_pct}% max'
                })
                return validation_result

        # 3. Cash reserve requirements
        if side == "BUY":
            remaining_cash = self.cash_balance - (order_value + commission)
            required_reserve = self.total_value * (self.min_cash_reserve_pct / 100)

            if remaining_cash < required_reserve:
                validation_result.update({
                    'valid': False,
                    'reason': f'Cash reserve violation: ${remaining_cash:.2f} < ${required_reserve:.2f} required'
                })
                return validation_result

        # 4. Daily loss limits
        current_pnl_pct = self.total_pnl_pct
        if current_pnl_pct < -self.max_daily_loss_pct:
            validation_result.update({
                'valid': False,
                'reason': f'Daily loss limit exceeded: {current_pnl_pct:.1f}% < -{self.max_daily_loss_pct}% max'
            })
            return validation_result

        # 5. Calculate risk metrics for approved orders
        validation_result['risk_metrics'] = {
            'position_size_pct': (new_position_value / self.total_value) * 100 if side == "BUY" else 0,
            'remaining_cash_pct': ((self.cash_balance - (order_value + commission if side == "BUY" else -(order_value - commission))) / self.total_value) * 100,
            'portfolio_concentration': len(self.positions) + (1 if side == "BUY" and symbol not in self.positions else 0),
            'current_leverage': 1.0,  # No leverage in current implementation
            'order_impact_pct': (order_value / self.total_value) * 100
        }

        return validation_result

    def _save_position(self, position: Position):
        """Save position to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO positions
                (position_id, symbol, quantity, avg_price, entry_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (position.position_id, position.symbol, position.quantity,
                  position.avg_price, position.entry_date.isoformat(),
                  position.last_updated.isoformat()))

    def _save_trade(self, trade: Trade):
        """Save trade to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO trades
                (trade_id, symbol, quantity, price, side, trade_date, commission, position_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (trade.trade_id, trade.symbol, trade.quantity, trade.price,
                  trade.side, trade.trade_date.isoformat(), trade.commission,
                  trade.position_id))

    def _save_cash_balance(self):
        """Save cash balance to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO account_info (cash_balance, last_updated)
                VALUES (?, ?)
            ''', (self.cash_balance, datetime.now().isoformat()))

    async def update_prices(self):
        """Update current prices for all positions"""
        if not self.positions:
            return

        symbols = list(self.positions.keys())

        # Get current prices
        for symbol in symbols:
            try:
                price_data = await self.data_manager.get_real_time_price(symbol)
                if price_data and price_data['last'] > 0:
                    self.positions[symbol].update_price(price_data['last'])
            except Exception as e:
                logger.warning(f"Failed to update price for {symbol}: {e}")

    def add_trade(self, symbol: str, quantity: int, price: float,
                  commission: float = 1.0) -> Optional[Trade]:
        """
        Add a new trade with comprehensive pre-trade risk validation
        Returns the Trade object if successful, None if rejected
        """
        # Comprehensive pre-trade risk validation
        validation = self.validate_order(symbol, quantity, price, commission)

        if not validation['valid']:
            # Log and store rejected order
            rejection_record = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'commission': commission,
                'rejection_reason': validation['reason'],
                'risk_metrics': validation.get('risk_metrics', {})
            }
            self.rejected_orders.append(rejection_record)

            logger.error(f"Order rejected - {validation['reason']}")
            logger.info(f"Risk metrics: {validation.get('risk_metrics', {})}")
            return None

        # Order approved - log risk metrics
        logger.info(f"Order approved for {symbol}: {validation['risk_metrics']}")

        side = "BUY" if quantity > 0 else "SELL"
        abs_quantity = abs(quantity)

        # Create trade
        trade = Trade(symbol=symbol, quantity=abs_quantity, price=price,
                     side=side, commission=commission)

        # Update position
        if symbol in self.positions:
            position = self.positions[symbol]

            if side == "BUY":
                # Add to position
                new_quantity = position.quantity + abs_quantity
                new_avg_price = ((position.quantity * position.avg_price) +
                               (abs_quantity * price)) / new_quantity
                position.quantity = new_quantity
                position.avg_price = new_avg_price

                # Update cash
                self.cash_balance -= (abs_quantity * price + commission)

            else:  # SELL
                # Reduce position
                position.quantity -= abs_quantity

                # Update cash
                self.cash_balance += (abs_quantity * price - commission)

                # Remove position if quantity is 0
                if position.quantity == 0:
                    del self.positions[symbol]

            if symbol in self.positions:
                self._save_position(self.positions[symbol])
        else:
            # New position (must be a BUY)
            if side == "BUY":
                position = Position(symbol=symbol, quantity=abs_quantity, avg_price=price)
                self.positions[symbol] = position
                self.cash_balance -= (abs_quantity * price + commission)
                self._save_position(position)

        # Save trade and cash balance
        self._save_trade(trade)
        self._save_cash_balance()
        self.trades.append(trade)

        logger.info(f"Trade executed: {side} {abs_quantity} {symbol} @ ${price:.2f}")
        return trade

    async def place_market_order_ib(self, symbol: str, quantity: int) -> bool:
        """Place market order through IB (paper trading)"""
        if not self.use_ib:
            logger.warning("IB not enabled")
            return False

        try:
            client = await create_ib_client(paper_trading=self.paper_trading)
            if not client.connected:
                return False

            action = "BUY" if quantity > 0 else "SELL"
            result = await client.place_market_order(symbol, abs(quantity), action)

            client.disconnect()

            if result:
                logger.info(f"IB order placed: {result}")
                return True

        except Exception as e:
            logger.error(f"Failed to place IB order: {e}")

        return False

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)"""
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash_balance + positions_value

    @property
    def total_pnl(self) -> float:
        """Total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    @property
    def total_pnl_pct(self) -> float:
        """Total P&L as percentage of initial capital"""
        if self.initial_cash == 0:
            return 0
        return ((self.total_value / self.initial_cash) - 1) * 100

    def get_positions_df(self) -> pd.DataFrame:
        """Get positions as DataFrame"""
        if not self.positions:
            return pd.DataFrame()

        positions_data = [pos.to_dict() for pos in self.positions.values()]
        return pd.DataFrame(positions_data)

    def get_trades_df(self) -> pd.DataFrame:
        """Get trade history as DataFrame"""
        if not self.trades:
            return pd.DataFrame()

        trades_data = [trade.to_dict() for trade in self.trades]
        return pd.DataFrame(trades_data)

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary"""
        return {
            'total_value': self.total_value,
            'cash_balance': self.cash_balance,
            'positions_value': self.total_value - self.cash_balance,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'num_positions': len(self.positions),
            'num_trades': len(self.trades),
            'num_rejected_orders': len(self.rejected_orders),
            'last_updated': datetime.now()
        }

    def get_risk_summary(self) -> Dict:
        """Get comprehensive risk summary"""
        return {
            'risk_parameters': {
                'max_position_size_pct': self.max_position_size_pct,
                'max_sector_exposure_pct': self.max_sector_exposure_pct,
                'max_daily_loss_pct': self.max_daily_loss_pct,
                'max_portfolio_leverage': self.max_portfolio_leverage,
                'min_cash_reserve_pct': self.min_cash_reserve_pct
            },
            'current_metrics': {
                'total_pnl_pct': self.total_pnl_pct,
                'cash_reserve_pct': (self.cash_balance / self.total_value) * 100,
                'num_positions': len(self.positions),
                'largest_position_pct': max([(pos.market_value / self.total_value) * 100 for pos in self.positions.values()]) if self.positions else 0,
                'portfolio_concentration': len(self.positions)
            },
            'order_statistics': {
                'total_orders_attempted': len(self.trades) + len(self.rejected_orders),
                'successful_orders': len(self.trades),
                'rejected_orders': len(self.rejected_orders),
                'rejection_rate_pct': (len(self.rejected_orders) / (len(self.trades) + len(self.rejected_orders))) * 100 if (len(self.trades) + len(self.rejected_orders)) > 0 else 0
            }
        }

    def get_rejected_orders(self) -> List[Dict]:
        """Get list of rejected orders with reasons"""
        return self.rejected_orders.copy()

    async def sync_with_ib(self):
        """Sync portfolio with IB account (if connected)"""
        if not self.use_ib:
            return

        try:
            portfolio_data = await self.data_manager.get_portfolio_data()

            if portfolio_data['positions']:
                logger.info("Syncing portfolio with IB...")

                # Update positions based on IB data
                ib_positions = {pos['symbol']: pos for pos in portfolio_data['positions']}

                for symbol, ib_pos in ib_positions.items():
                    if ib_pos['position'] != 0:
                        # Update or create position
                        if symbol in self.positions:
                            self.positions[symbol].quantity = ib_pos['position']
                            self.positions[symbol].avg_price = ib_pos['averageCost']
                            self.positions[symbol].current_price = ib_pos['marketPrice']
                        else:
                            # New position from IB
                            position = Position(
                                symbol=symbol,
                                quantity=ib_pos['position'],
                                avg_price=ib_pos['averageCost']
                            )
                            position.current_price = ib_pos['marketPrice']
                            self.positions[symbol] = position

                # Update cash from account info
                if 'account_info' in portfolio_data:
                    cash_info = portfolio_data['account_info'].get('TotalCashValue')
                    if cash_info:
                        self.cash_balance = float(cash_info['value'])

        except Exception as e:
            logger.error(f"Failed to sync with IB: {e}")

# Utility functions for Streamlit integration
def create_sample_portfolio() -> PortfolioManager:
    """Create a sample portfolio for testing"""
    pm = PortfolioManager(initial_cash=100000, use_ib=False)

    # Add some sample trades
    pm.add_trade("AAPL", 100, 150.0, commission=1.0)
    pm.add_trade("NVDA", 50, 800.0, commission=1.0)
    pm.add_trade("SPY", 200, 400.0, commission=1.0)

    return pm