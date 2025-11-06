"""
Database Access Layer for PostgreSQL
High-performance data access with connection pooling and caching optimized for quantitative trading
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal
import logging
from functools import wraps
import json

from .pg_config import PostgreSQLManager, DatabaseConfig, get_database_manager
try:
    from src.core.portfolio_manager import Position, Trade
except ImportError:
    # Define minimal classes for independence
    from dataclasses import dataclass
    from datetime import datetime
    from typing import Optional

    @dataclass
    class Position:
        symbol: str
        quantity: int
        avg_price: float
        market_value: float = 0.0
        unrealized_pnl: float = 0.0

    @dataclass
    class Trade:
        symbol: str
        quantity: int
        price: float
        timestamp: datetime
        trade_type: str = "BUY"

logger = logging.getLogger(__name__)

@dataclass
class TradingPosition:
    """Enhanced position data from PostgreSQL"""
    position_id: str
    account_id: str
    symbol: str
    quantity: int
    avg_price: Decimal
    current_price: Optional[Decimal]
    market_value: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    unrealized_pnl_pct: Optional[Decimal]
    position_date: date
    last_updated: datetime
    is_active: bool

    def to_dict(self) -> Dict:
        """Convert to dictionary for compatibility with existing code"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': float(self.avg_price),
            'current_price': float(self.current_price) if self.current_price else 0.0,
            'market_value': float(self.market_value) if self.market_value else 0.0,
            'unrealized_pnl': float(self.unrealized_pnl) if self.unrealized_pnl else 0.0,
            'unrealized_pnl_pct': float(self.unrealized_pnl_pct) if self.unrealized_pnl_pct else 0.0,
            'side': 'LONG' if self.quantity > 0 else 'SHORT',
            'entry_date': self.position_date.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }

@dataclass
class TradingTrade:
    """Enhanced trade data from PostgreSQL"""
    trade_id: str
    account_id: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    trade_value: Decimal
    commission: Decimal
    net_value: Decimal
    execution_time: datetime
    strategy_name: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for compatibility with existing code"""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': float(self.price),
            'trade_value': float(self.trade_value),
            'commission': float(self.commission),
            'net_value': float(self.net_value),
            'trade_date': self.execution_time.isoformat()
        }

def handle_db_errors(func):
    """Decorator to handle database errors gracefully"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database operation failed in {func.__name__}: {e}")
            raise
    return wrapper

class TradingDataAccess:
    """High-level data access layer for trading operations"""

    def __init__(self, account_id: str, db_manager: PostgreSQLManager = None):
        self.account_id = account_id
        self.db_manager = db_manager or get_database_manager()

    @handle_db_errors
    async def get_account_summary(self) -> Dict[str, Any]:
        """Get complete account summary with latest balances and positions"""
        query = """
        WITH latest_balance AS (
            SELECT *
            FROM trading.account_balances
            WHERE account_id = $1
            ORDER BY timestamp DESC
            LIMIT 1
        ),
        position_summary AS (
            SELECT
                COUNT(*) as num_positions,
                COALESCE(SUM(market_value), 0) as total_positions_value,
                COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl
            FROM trading.positions
            WHERE account_id = $1 AND is_active = TRUE AND quantity != 0
        )
        SELECT
            lb.cash_balance,
            lb.total_equity,
            lb.day_pnl,
            lb.unrealized_pnl,
            lb.realized_pnl,
            ps.num_positions,
            ps.total_positions_value,
            ps.total_unrealized_pnl,
            lb.timestamp as last_updated
        FROM latest_balance lb
        CROSS JOIN position_summary ps
        """

        result = await self.db_manager.execute_query(query, (self.account_id,))

        if not result:
            return {
                'cash_balance': 0.0,
                'total_equity': 0.0,
                'total_value': 0.0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'num_positions': 0,
                'num_trades': 0,
                'last_updated': datetime.now()
            }

        data = result[0]
        total_value = float(data['total_equity'] or 0)
        cash_balance = float(data['cash_balance'] or 0)

        # Get initial capital for percentage calculation
        initial_capital = await self._get_initial_capital()
        total_pnl_pct = ((total_value / initial_capital) - 1) * 100 if initial_capital > 0 else 0

        # Get total trade count
        trade_count = await self._get_trade_count()

        return {
            'cash_balance': cash_balance,
            'total_equity': total_value,
            'total_value': total_value,
            'positions_value': float(data['total_positions_value'] or 0),
            'total_pnl': float(data['total_unrealized_pnl'] or 0),
            'total_pnl_pct': total_pnl_pct,
            'day_pnl': float(data['day_pnl'] or 0),
            'realized_pnl': float(data['realized_pnl'] or 0),
            'unrealized_pnl': float(data['unrealized_pnl'] or 0),
            'num_positions': int(data['num_positions'] or 0),
            'num_trades': trade_count,
            'last_updated': data['last_updated']
        }

    @handle_db_errors
    async def get_positions(self, active_only: bool = True) -> List[TradingPosition]:
        """Get all positions for the account"""
        query = """
        SELECT
            position_id, account_id, symbol, quantity, avg_price,
            current_price, market_value, unrealized_pnl, unrealized_pnl_pct,
            position_date, last_updated, is_active
        FROM trading.positions
        WHERE account_id = $1
        """

        params = [self.account_id]

        if active_only:
            query += " AND is_active = TRUE AND quantity != 0"

        query += " ORDER BY symbol"

        result = await self.db_manager.execute_query(query, params)

        return [
            TradingPosition(
                position_id=row['position_id'],
                account_id=row['account_id'],
                symbol=row['symbol'],
                quantity=row['quantity'],
                avg_price=row['avg_price'],
                current_price=row['current_price'],
                market_value=row['market_value'],
                unrealized_pnl=row['unrealized_pnl'],
                unrealized_pnl_pct=row['unrealized_pnl_pct'],
                position_date=row['position_date'],
                last_updated=row['last_updated'],
                is_active=row['is_active']
            )
            for row in result
        ]

    @handle_db_errors
    async def get_trades(self, limit: int = 100, symbol: str = None) -> List[TradingTrade]:
        """Get trade history for the account"""
        query = """
        SELECT
            trade_id, account_id, symbol, side, quantity, price,
            trade_value, commission, net_value, execution_time, strategy_name
        FROM trading.trades
        WHERE account_id = $1
        """

        params = [self.account_id]

        if symbol:
            query += " AND symbol = $2"
            params.append(symbol)

        query += " ORDER BY execution_time DESC"

        if limit:
            query += f" LIMIT ${len(params) + 1}"
            params.append(limit)

        result = await self.db_manager.execute_query(query, params)

        return [
            TradingTrade(
                trade_id=row['trade_id'],
                account_id=row['account_id'],
                symbol=row['symbol'],
                side=row['side'],
                quantity=row['quantity'],
                price=row['price'],
                trade_value=row['trade_value'],
                commission=row['commission'],
                net_value=row['net_value'],
                execution_time=row['execution_time'],
                strategy_name=row['strategy_name']
            )
            for row in result
        ]

    @handle_db_errors
    async def add_trade(self, symbol: str, quantity: int, price: float,
                       commission: float = 1.0, strategy_name: str = None) -> Optional[str]:
        """Add a new trade and update positions"""
        side = "BUY" if quantity > 0 else "SELL"
        abs_quantity = abs(quantity)

        async with self.db_manager.get_connection() as conn:
            async with conn.transaction():
                try:
                    # Check for sufficient funds/shares
                    if side == "BUY":
                        if not await self._check_sufficient_funds(abs_quantity * price + commission):
                            logger.error("Insufficient funds for trade")
                            return None
                    else:  # SELL
                        if not await self._check_sufficient_shares(symbol, abs_quantity):
                            logger.error("Insufficient shares for trade")
                            return None

                    # Insert trade
                    trade_query = """
                    INSERT INTO trading.trades (
                        account_id, symbol, side, quantity, price, commission,
                        execution_time, strategy_name, data_source
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING trade_id
                    """

                    trade_result = await conn.fetch(
                        trade_query,
                        self.account_id, symbol, side, abs_quantity, price,
                        commission, datetime.now(), strategy_name, 'SYSTEM'
                    )

                    trade_id = trade_result[0]['trade_id']

                    # Update position
                    await self._update_position_from_trade(conn, symbol, quantity, price)

                    # Update account balance
                    net_change = -(abs_quantity * price + commission) if side == "BUY" else (abs_quantity * price - commission)
                    await self._update_account_balance(conn, net_change)

                    logger.info(f"Trade executed: {side} {abs_quantity} {symbol} @ ${price:.2f}")
                    return trade_id

                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
                    raise

    @handle_db_errors
    async def update_position_prices(self, price_updates: Dict[str, float]):
        """Update current prices for multiple positions"""
        if not price_updates:
            return

        # Build update query for batch update
        query = """
        UPDATE trading.positions
        SET current_price = $2, last_updated = CURRENT_TIMESTAMP
        WHERE account_id = $1 AND symbol = $3 AND is_active = TRUE
        """

        updates = []
        for symbol, price in price_updates.items():
            updates.append((query, (self.account_id, price, symbol)))

        await self.db_manager.execute_transaction(updates)

        logger.info(f"Updated prices for {len(price_updates)} positions")

    @handle_db_errors
    async def get_position_by_symbol(self, symbol: str) -> Optional[TradingPosition]:
        """Get specific position by symbol"""
        positions = await self.get_positions()
        for position in positions:
            if position.symbol == symbol:
                return position
        return None

    @handle_db_errors
    async def get_portfolio_performance(self, days_back: int = 30) -> pd.DataFrame:
        """Get portfolio performance over time"""
        query = """
        SELECT
            snapshot_date,
            total_equity,
            cash_balance,
            positions_value,
            total_pnl,
            total_return_pct,
            num_positions
        FROM analytics.portfolio_snapshots
        WHERE account_id = $1
            AND snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY snapshot_date
        """

        result = await self.db_manager.execute_query(query % days_back, (self.account_id,))

        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result)
        df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
        return df.set_index('snapshot_date')

    # Helper methods

    async def _get_initial_capital(self) -> float:
        """Get initial capital for the account"""
        query = "SELECT initial_capital FROM trading.accounts WHERE account_id = $1"
        result = await self.db_manager.execute_query(query, (self.account_id,))
        return float(result[0]['initial_capital']) if result else 100000.0

    async def _get_trade_count(self) -> int:
        """Get total number of trades"""
        query = "SELECT COUNT(*) as count FROM trading.trades WHERE account_id = $1"
        result = await self.db_manager.execute_query(query, (self.account_id,))
        return result[0]['count'] if result else 0

    async def _check_sufficient_funds(self, required_amount: float) -> bool:
        """Check if account has sufficient funds"""
        query = """
        SELECT cash_balance
        FROM trading.account_balances
        WHERE account_id = $1
        ORDER BY timestamp DESC
        LIMIT 1
        """
        result = await self.db_manager.execute_query(query, (self.account_id,))
        current_cash = float(result[0]['cash_balance']) if result else 0
        return current_cash >= required_amount

    async def _check_sufficient_shares(self, symbol: str, required_quantity: int) -> bool:
        """Check if account has sufficient shares to sell"""
        query = """
        SELECT quantity
        FROM trading.positions
        WHERE account_id = $1 AND symbol = $2 AND is_active = TRUE
        """
        result = await self.db_manager.execute_query(query, (self.account_id, symbol))
        current_quantity = result[0]['quantity'] if result else 0
        return current_quantity >= required_quantity

    async def _update_position_from_trade(self, conn, symbol: str, quantity: int, price: float):
        """Update or create position based on trade"""
        # Check if position exists
        check_query = """
        SELECT position_id, quantity, avg_price
        FROM trading.positions
        WHERE account_id = $1 AND symbol = $2 AND is_active = TRUE
        """
        existing = await conn.fetch(check_query, self.account_id, symbol)

        if existing:
            # Update existing position
            pos = existing[0]
            old_quantity = pos['quantity']
            old_avg_price = float(pos['avg_price'])

            new_quantity = old_quantity + quantity

            if new_quantity == 0:
                # Close position
                update_query = """
                UPDATE trading.positions
                SET quantity = 0, is_active = FALSE, last_updated = CURRENT_TIMESTAMP
                WHERE position_id = $1
                """
                await conn.execute(update_query, pos['position_id'])
            else:
                # Update position with new average price
                if quantity > 0:  # Adding to position
                    new_avg_price = ((old_quantity * old_avg_price) + (quantity * price)) / new_quantity
                else:  # Reducing position, keep same avg price
                    new_avg_price = old_avg_price

                update_query = """
                UPDATE trading.positions
                SET quantity = $1, avg_price = $2, last_updated = CURRENT_TIMESTAMP
                WHERE position_id = $3
                """
                await conn.execute(update_query, new_quantity, new_avg_price, pos['position_id'])
        else:
            # Create new position (only for buys)
            if quantity > 0:
                insert_query = """
                INSERT INTO trading.positions (
                    account_id, symbol, quantity, avg_price, current_price,
                    position_date, last_updated, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                """
                await conn.execute(
                    insert_query,
                    self.account_id, symbol, quantity, price, price,
                    date.today(), datetime.now()
                )

    async def _update_account_balance(self, conn, net_change: float):
        """Update account cash balance"""
        # Get current balance
        current_query = """
        SELECT cash_balance, total_equity
        FROM trading.account_balances
        WHERE account_id = $1
        ORDER BY timestamp DESC
        LIMIT 1
        """
        result = await conn.fetch(current_query, self.account_id)

        if result:
            current_cash = float(result[0]['cash_balance'])
            current_equity = float(result[0]['total_equity'])
        else:
            # Get from account initial capital
            account_query = "SELECT initial_capital FROM trading.accounts WHERE account_id = $1"
            account_result = await conn.fetch(account_query, self.account_id)
            current_cash = current_equity = float(account_result[0]['initial_capital'])

        new_cash = current_cash + net_change
        new_equity = current_equity + net_change  # Simplified

        # Insert new balance record
        insert_query = """
        INSERT INTO trading.account_balances (
            account_id, cash_balance, total_equity, timestamp, data_source
        )
        VALUES ($1, $2, $3, $4, 'SYSTEM')
        """
        await conn.execute(insert_query, self.account_id, new_cash, new_equity, datetime.now())

class MarketDataAccess:
    """Market data access layer"""

    def __init__(self, db_manager: PostgreSQLManager = None):
        self.db_manager = db_manager or get_database_manager()

    @handle_db_errors
    async def store_daily_prices(self, symbol: str, price_data: pd.DataFrame):
        """Store daily price data"""
        if price_data.empty:
            return

        # Prepare data for insertion
        insert_data = []
        for idx, row in price_data.iterrows():
            insert_data.append((
                symbol,
                idx.date() if hasattr(idx, 'date') else idx,
                row['Open'] if 'Open' in row else row['price'],
                row['High'] if 'High' in row else row['price'],
                row['Low'] if 'Low' in row else row['price'],
                row['Close'] if 'Close' in row else row['price'],
                row.get('Adj Close', row['Close'] if 'Close' in row else row['price']),
                row.get('Volume', 0),
                'SYSTEM'
            ))

        # Batch insert with conflict handling
        query = """
        INSERT INTO market_data.daily_prices (
            symbol, price_date, open_price, high_price, low_price,
            close_price, adjusted_close, volume, data_source
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (symbol, price_date) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            adjusted_close = EXCLUDED.adjusted_close,
            volume = EXCLUDED.volume,
            data_source = EXCLUDED.data_source
        """

        await self.db_manager.execute_many(query, insert_data)
        logger.info(f"Stored {len(insert_data)} daily price records for {symbol}")

    @handle_db_errors
    async def get_price_history(self, symbol: str, days_back: int = 252) -> pd.DataFrame:
        """Get historical price data"""
        query = """
        SELECT
            price_date,
            open_price,
            high_price,
            low_price,
            close_price,
            adjusted_close,
            volume
        FROM market_data.daily_prices
        WHERE symbol = $1
            AND price_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY price_date
        """

        result = await self.db_manager.execute_query(query % days_back, (symbol,))

        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result)
        df['price_date'] = pd.to_datetime(df['price_date'])
        return df.set_index('price_date')

class BacktestingDataAccess:
    """Backtesting data access layer"""

    def __init__(self, db_manager: PostgreSQLManager = None):
        self.db_manager = db_manager or get_database_manager()

    @handle_db_errors
    async def store_backtest_run(self, run_name: str, strategy_name: str, symbol: str,
                                start_date: date, end_date: date, initial_capital: float,
                                strategy_params: Dict) -> str:
        """Store backtest run configuration"""
        query = """
        INSERT INTO backtesting.backtest_runs (
            run_name, strategy_name, symbol, start_date, end_date,
            initial_capital, strategy_params, run_status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'PENDING')
        RETURNING run_id
        """

        result = await self.db_manager.execute_query(
            query,
            (run_name, strategy_name, symbol, start_date, end_date,
             initial_capital, json.dumps(strategy_params))
        )

        return result[0]['run_id']

    @handle_db_errors
    async def store_backtest_results(self, run_id: str, results: Dict):
        """Store backtest results"""
        query = """
        INSERT INTO backtesting.backtest_results (
            run_id, total_return, total_return_pct, sharpe_ratio, max_drawdown,
            volatility, total_trades, winning_trades, losing_trades, win_rate,
            avg_win, avg_loss, profit_factor, starting_value, ending_value
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """

        await self.db_manager.execute_command(query, (
            run_id,
            results.get('total_return', 0),
            results.get('total_return_pct', 0),
            results.get('sharpe_ratio'),
            results.get('max_drawdown'),
            results.get('volatility'),
            results.get('total_trades', 0),
            results.get('winning_trades', 0),
            results.get('losing_trades', 0),
            results.get('win_rate'),
            results.get('avg_win'),
            results.get('avg_loss'),
            results.get('profit_factor'),
            results.get('starting_value'),
            results.get('ending_value')
        ))

        # Update run status
        await self.db_manager.execute_command(
            "UPDATE backtesting.backtest_runs SET run_status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP WHERE run_id = $1",
            (run_id,)
        )

    @handle_db_errors
    async def get_strategy_performance(self, strategy_name: str = None) -> pd.DataFrame:
        """Get strategy performance comparison"""
        query = """
        SELECT
            br.strategy_name,
            br.symbol,
            br.start_date,
            br.end_date,
            res.total_return_pct,
            res.sharpe_ratio,
            res.max_drawdown,
            res.win_rate,
            res.total_trades,
            br.created_at
        FROM backtesting.backtest_runs br
        JOIN backtesting.backtest_results res ON br.run_id = res.run_id
        WHERE br.run_status = 'COMPLETED'
        """

        params = []
        if strategy_name:
            query += " AND br.strategy_name = $1"
            params.append(strategy_name)

        query += " ORDER BY br.created_at DESC"

        result = await self.db_manager.execute_query(query, params)

        if not result:
            return pd.DataFrame()

        return pd.DataFrame(result)