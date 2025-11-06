"""
Enhanced Portfolio Manager with PostgreSQL Integration
Provides high-performance portfolio management with advanced analytics and real-time capabilities
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import logging
from dataclasses import dataclass
from decimal import Decimal

try:
    from src.database.pg_config import DatabaseConfig, get_database_manager, PostgreSQLManager
    from src.database.data_access import TradingDataAccess, MarketDataAccess, TradingPosition, TradingTrade
    from src.binance.rest_client import BinanceRESTClient
    from src.binance.data_manager import BinanceDataManager
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from src.database.pg_config import DatabaseConfig, get_database_manager, PostgreSQLManager
    from src.database.data_access import TradingDataAccess, MarketDataAccess, TradingPosition, TradingTrade
    from src.binance.rest_client import BinanceRESTClient
    from src.binance.data_manager import BinanceDataManager

logger = logging.getLogger(__name__)

@dataclass
class PortfolioSummary:
    """Comprehensive portfolio summary"""
    total_equity: float
    cash_balance: float
    positions_value: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    num_positions: int
    num_trades: int
    largest_position_pct: float
    long_exposure: float
    short_exposure: float
    beta: float
    sharpe_ratio: Optional[float]
    last_updated: datetime

class PostgreSQLPortfolioManager:
    """Enhanced portfolio manager using PostgreSQL for data storage and analytics"""

    def __init__(self, account_id: str = None, db_config: DatabaseConfig = None,
                 testnet: bool = True, paper_trading: bool = True):
        # Database setup
        self.db_config = db_config or DatabaseConfig()
        self.db_manager = get_database_manager(self.db_config)
        self.account_id = account_id

        # Data access layers
        self.trading_access = None  # Will be initialized when account_id is set
        self.market_access = MarketDataAccess(self.db_manager)

        # Market data manager for real-time prices (Binance)
        self.rest_client = BinanceRESTClient(testnet=testnet)
        self.data_manager = None  # Will be initialized in async initialize()

        # Configuration
        self.testnet = testnet
        self.paper_trading = paper_trading

        # Cache for performance
        self._positions_cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 30  # seconds

    async def initialize(self, account_name: str = "PostgreSQL Portfolio",
                        initial_capital: float = 100000.0) -> str:
        """Initialize the portfolio manager and create/get account"""
        await self.db_manager.initialize()

        if not self.account_id:
            # Create new account
            self.account_id = await self._create_account(account_name, initial_capital)
            logger.info(f"Created new account: {self.account_id}")

        # Initialize data access layer
        self.trading_access = TradingDataAccess(self.account_id, self.db_manager)

        # Initialize Binance data manager for WebSocket price feeds
        self.data_manager = BinanceDataManager(testnet=self.testnet)

        return self.account_id

    async def _create_account(self, account_name: str, initial_capital: float) -> str:
        """Create a new trading account"""
        query = """
        INSERT INTO trading.accounts (account_name, account_type, initial_capital, currency)
        VALUES ($1, $2, $3, $4)
        RETURNING account_id
        """

        account_type = "PAPER" if self.paper_trading else "LIVE"
        result = await self.db_manager.execute_query(
            query, (account_name, account_type, initial_capital, "USD")
        )

        account_id = result[0]['account_id']

        # Create initial balance record
        balance_query = """
        INSERT INTO trading.account_balances (account_id, cash_balance, total_equity, data_source)
        VALUES ($1, $2, $3, $4)
        """
        await self.db_manager.execute_command(
            balance_query, (account_id, initial_capital, initial_capital, 'SYSTEM')
        )

        return account_id

    async def add_trade(self, symbol: str, quantity: int, price: float,
                       commission: float = 1.0, strategy_name: str = None) -> Optional[str]:
        """Add a trade to the portfolio"""
        if not self.trading_access:
            raise RuntimeError("Portfolio manager not initialized. Call initialize() first.")

        trade_id = await self.trading_access.add_trade(
            symbol, quantity, price, commission, strategy_name
        )

        # Invalidate cache
        self._invalidate_cache()

        return trade_id

    async def get_positions(self, force_refresh: bool = False) -> List[TradingPosition]:
        """Get current positions with caching"""
        if not self.trading_access:
            raise RuntimeError("Portfolio manager not initialized")

        # Check cache
        if not force_refresh and self._is_cache_valid():
            return list(self._positions_cache.values())

        positions = await self.trading_access.get_positions()

        # Update cache
        self._positions_cache = {pos.symbol: pos for pos in positions}
        self._cache_timestamp = datetime.now()

        return positions

    async def get_positions_df(self) -> pd.DataFrame:
        """Get positions as DataFrame for compatibility with existing code"""
        positions = await self.get_positions()

        if not positions:
            return pd.DataFrame()

        data = [pos.to_dict() for pos in positions]
        return pd.DataFrame(data)

    async def get_trades(self, limit: int = 100, symbol: str = None) -> List[TradingTrade]:
        """Get trade history"""
        if not self.trading_access:
            raise RuntimeError("Portfolio manager not initialized")

        return await self.trading_access.get_trades(limit, symbol)

    async def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame for compatibility"""
        trades = await self.get_trades()

        if not trades:
            return pd.DataFrame()

        data = [trade.to_dict() for trade in trades]
        return pd.DataFrame(data)

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get comprehensive portfolio summary"""
        if not self.trading_access:
            raise RuntimeError("Portfolio manager not initialized")

        # Get basic summary from database
        summary = await self.trading_access.get_account_summary()

        # Calculate additional metrics
        positions = await self.get_positions()

        # Calculate exposures
        long_exposure = sum(float(pos.market_value or 0) for pos in positions if pos.quantity > 0)
        short_exposure = sum(abs(float(pos.market_value or 0)) for pos in positions if pos.quantity < 0)

        # Calculate largest position percentage
        total_equity = summary['total_equity']
        largest_position_pct = 0.0
        if positions and total_equity > 0:
            largest_position = max(positions, key=lambda p: abs(float(p.market_value or 0)))
            largest_position_pct = (abs(float(largest_position.market_value or 0)) / total_equity) * 100

        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = await self._calculate_sharpe_ratio()

        return PortfolioSummary(
            total_equity=summary['total_equity'],
            cash_balance=summary['cash_balance'],
            positions_value=summary.get('positions_value', 0.0),
            total_pnl=summary['total_pnl'],
            total_pnl_pct=summary['total_pnl_pct'],
            day_pnl=summary.get('day_pnl', 0.0),
            realized_pnl=summary.get('realized_pnl', 0.0),
            unrealized_pnl=summary.get('unrealized_pnl', 0.0),
            num_positions=summary['num_positions'],
            num_trades=summary['num_trades'],
            largest_position_pct=largest_position_pct,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            beta=1.0,  # Placeholder - would need market data for proper calculation
            sharpe_ratio=sharpe_ratio,
            last_updated=summary['last_updated']
        )

    async def update_prices(self, symbols: List[str] = None):
        """Update current prices for positions"""
        if not self.trading_access:
            return

        positions = await self.get_positions()

        if not positions:
            return

        # Get symbols to update
        if symbols is None:
            symbols = [pos.symbol for pos in positions]

        price_updates = {}

        # Get current prices from Binance
        for symbol in symbols:
            try:
                # Try WebSocket data first (if data_manager is initialized)
                if self.data_manager:
                    price = await self.data_manager.get_latest_price(symbol)
                    if price:
                        price_updates[symbol] = price
                        continue

                # Fallback to REST API
                price = await self.rest_client.get_current_price(symbol)
                if price > 0:
                    price_updates[symbol] = price
            except Exception as e:
                logger.warning(f"Failed to update price for {symbol}: {e}")

        # Batch update prices in database
        if price_updates:
            await self.trading_access.update_position_prices(price_updates)
            # Invalidate cache to force refresh
            self._invalidate_cache()

    async def get_portfolio_performance(self, days_back: int = 30) -> pd.DataFrame:
        """Get portfolio performance over time"""
        if not self.trading_access:
            return pd.DataFrame()

        return await self.trading_access.get_portfolio_performance(days_back)

    async def get_risk_metrics(self) -> Dict[str, float]:
        """Calculate portfolio risk metrics"""
        positions = await self.get_positions()

        if not positions:
            return {}

        # Calculate concentration
        total_value = sum(abs(float(pos.market_value or 0)) for pos in positions)
        concentration = 0.0
        if total_value > 0:
            largest_position = max(positions, key=lambda p: abs(float(p.market_value or 0)))
            concentration = (abs(float(largest_position.market_value or 0)) / total_value) * 100

        # Calculate sector concentration (simplified)
        sector_exposure = {}
        for pos in positions:
            # In a real implementation, you'd get sector data from database
            sector = "Technology"  # Placeholder
            sector_exposure[sector] = sector_exposure.get(sector, 0) + abs(float(pos.market_value or 0))

        max_sector_exposure = max(sector_exposure.values()) if sector_exposure else 0
        sector_concentration = (max_sector_exposure / total_value * 100) if total_value > 0 else 0

        return {
            'position_concentration': concentration,
            'sector_concentration': sector_concentration,
            'num_positions': len(positions),
            'long_short_ratio': self._calculate_long_short_ratio(positions),
            'total_exposure': total_value
        }

    async def get_performance_attribution(self) -> Dict[str, Dict]:
        """Get performance attribution by position"""
        positions = await self.get_positions()

        attribution = {}
        for pos in positions:
            attribution[pos.symbol] = {
                'pnl_contribution': float(pos.unrealized_pnl or 0),
                'pnl_pct_contribution': float(pos.unrealized_pnl_pct or 0),
                'weight': float(pos.market_value or 0),
                'side': 'LONG' if pos.quantity > 0 else 'SHORT'
            }

        return attribution

    async def store_daily_snapshot(self):
        """Store daily portfolio snapshot for historical analysis"""
        summary = await self.get_portfolio_summary()

        query = """
        INSERT INTO analytics.portfolio_snapshots (
            account_id, snapshot_date, total_equity, cash_balance, positions_value,
            total_pnl, total_return_pct, num_positions, largest_position_pct,
            sharpe_ratio
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (account_id, snapshot_date) DO UPDATE SET
            total_equity = EXCLUDED.total_equity,
            cash_balance = EXCLUDED.cash_balance,
            positions_value = EXCLUDED.positions_value,
            total_pnl = EXCLUDED.total_pnl,
            total_return_pct = EXCLUDED.total_return_pct,
            num_positions = EXCLUDED.num_positions,
            largest_position_pct = EXCLUDED.largest_position_pct,
            sharpe_ratio = EXCLUDED.sharpe_ratio
        """

        await self.db_manager.execute_command(query, (
            self.account_id,
            datetime.now().date(),
            summary.total_equity,
            summary.cash_balance,
            summary.positions_value,
            summary.total_pnl,
            summary.total_pnl_pct,
            summary.num_positions,
            summary.largest_position_pct,
            summary.sharpe_ratio
        ))

    # Helper methods

    def _is_cache_valid(self) -> bool:
        """Check if positions cache is still valid"""
        if not self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl

    def _invalidate_cache(self):
        """Invalidate positions cache"""
        self._cache_timestamp = None
        self._positions_cache.clear()

    async def _calculate_sharpe_ratio(self, days_back: int = 252) -> Optional[float]:
        """Calculate Sharpe ratio based on portfolio performance"""
        try:
            # Get portfolio performance data
            perf_df = await self.get_portfolio_performance(days_back)

            if perf_df.empty or len(perf_df) < 2:
                return None

            # Calculate daily returns
            perf_df['daily_return'] = perf_df['total_equity'].pct_change()

            # Calculate Sharpe ratio (annualized)
            daily_returns = perf_df['daily_return'].dropna()

            if len(daily_returns) < 10:  # Need enough data points
                return None

            avg_return = daily_returns.mean() * 252  # Annualized
            return_std = daily_returns.std() * np.sqrt(252)  # Annualized

            # Risk-free rate (simplified as 0)
            risk_free_rate = 0.02  # 2% risk-free rate

            if return_std > 0:
                return (avg_return - risk_free_rate) / return_std

            return None

        except Exception as e:
            logger.warning(f"Failed to calculate Sharpe ratio: {e}")
            return None

    def _calculate_long_short_ratio(self, positions: List[TradingPosition]) -> float:
        """Calculate long/short ratio"""
        long_value = sum(float(pos.market_value or 0) for pos in positions if pos.quantity > 0)
        short_value = sum(abs(float(pos.market_value or 0)) for pos in positions if pos.quantity < 0)

        if short_value == 0:
            return float('inf') if long_value > 0 else 0

        return long_value / short_value

    # Compatibility methods for existing code

    @property
    def total_value(self) -> float:
        """Sync property for compatibility - use get_portfolio_summary() for async"""
        # This is a blocking call - should be avoided in async code
        try:
            loop = asyncio.get_event_loop()
            summary = loop.run_until_complete(self.get_portfolio_summary())
            return summary.total_equity
        except Exception:
            return 0.0

    @property
    def initial_cash(self) -> float:
        """Get initial cash from account"""
        try:
            loop = asyncio.get_event_loop()
            query = "SELECT initial_capital FROM trading.accounts WHERE account_id = $1"
            result = loop.run_until_complete(
                self.db_manager.execute_query(query, (self.account_id,))
            )
            return float(result[0]['initial_capital']) if result else 100000.0
        except Exception:
            return 100000.0

    async def close(self):
        """Clean up resources"""
        if hasattr(self.data_manager, 'close_connections'):
            await self.data_manager.close_connections()

        if self.db_manager:
            await self.db_manager.close()

# Factory function for easy creation
async def create_portfolio_manager(account_name: str = "PostgreSQL Portfolio",
                                  initial_capital: float = 100000.0,
                                  use_ib: bool = True,
                                  paper_trading: bool = True,
                                  db_config: DatabaseConfig = None) -> PostgreSQLPortfolioManager:
    """Factory function to create and initialize portfolio manager"""
    manager = PostgreSQLPortfolioManager(
        db_config=db_config,
        use_ib=use_ib,
        paper_trading=paper_trading
    )

    await manager.initialize(account_name, initial_capital)

    return manager