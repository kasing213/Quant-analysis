"""
Binance Bot Persistence Layer
Handles saving/loading bot configurations, trades, and performance to PostgreSQL
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
import asyncpg
from ..database.pg_config import get_async_pool

logger = logging.getLogger(__name__)


class BotPersistence:
    """
    Manages persistence of bot configurations, state, trades, and metrics to PostgreSQL
    """

    def __init__(self):
        self.pool = None

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await get_async_pool()
            logger.info("Bot persistence initialized")
        except Exception as e:
            logger.error(f"Failed to initialize bot persistence: {e}")
            raise

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            logger.info("Bot persistence closed")

    # ===================================
    # BOT CONFIGURATION
    # ===================================

    async def save_bot_config(
        self,
        bot_id: str,
        bot_name: str,
        symbol: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        interval: str = "1m",
        capital: float = 1000.0,
        position_size: float = 100.0,
        risk_per_trade: float = 0.02,
        max_position_size: float = 0.1,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        drawdown_guard_pct: Optional[float] = None
    ) -> str:
        """
        Save or update bot configuration

        Returns:
            bot_id: The bot ID
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT binance.upsert_bot_config(
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                    )
                    """,
                    bot_id,
                    bot_name,
                    symbol,
                    strategy_name,
                    json.dumps(strategy_params),
                    interval,
                    Decimal(str(capital)),
                    Decimal(str(position_size)),
                    Decimal(str(risk_per_trade)),
                    Decimal(str(max_position_size)),
                    Decimal(str(stop_loss_pct)) if stop_loss_pct else None,
                    Decimal(str(take_profit_pct)) if take_profit_pct else None,
                    Decimal(str(trailing_stop_pct)) if trailing_stop_pct is not None else None,
                    Decimal(str(drawdown_guard_pct)) if drawdown_guard_pct is not None else None
                )
                logger.info(f"Saved bot config: {bot_id}")
                return result
        except Exception as e:
            logger.error(f"Failed to save bot config {bot_id}: {e}")
            raise

    async def get_bot_config(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get bot configuration by ID"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM binance.bot_configs
                    WHERE bot_id = $1
                    """,
                    bot_id
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get bot config {bot_id}: {e}")
            return None

    async def get_all_bot_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all bot configurations"""
        try:
            async with self.pool.acquire() as conn:
                query = "SELECT * FROM binance.bot_configs"
                if active_only:
                    query += " WHERE is_active = TRUE"
                query += " ORDER BY created_at DESC"

                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get bot configs: {e}")
            return []

    async def update_bot_status(
        self,
        bot_id: str,
        is_running: Optional[bool] = None,
        is_active: Optional[bool] = None
    ):
        """Update bot running/active status"""
        try:
            async with self.pool.acquire() as conn:
                updates = []
                params = [bot_id]
                param_count = 1

                if is_running is not None:
                    param_count += 1
                    updates.append(f"is_running = ${param_count}")
                    params.append(is_running)

                    if is_running:
                        param_count += 1
                        updates.append(f"last_started_at = ${param_count}")
                        params.append(datetime.now())
                    else:
                        param_count += 1
                        updates.append(f"last_stopped_at = ${param_count}")
                        params.append(datetime.now())

                if is_active is not None:
                    param_count += 1
                    updates.append(f"is_active = ${param_count}")
                    params.append(is_active)

                if updates:
                    query = f"""
                        UPDATE binance.bot_configs
                        SET {', '.join(updates)}
                        WHERE bot_id = $1
                    """
                    await conn.execute(query, *params)
                    logger.info(f"Updated bot status: {bot_id}")
        except Exception as e:
            logger.error(f"Failed to update bot status {bot_id}: {e}")
            raise

    async def delete_bot_config(self, bot_id: str):
        """Delete bot configuration (and cascade to related data)"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM binance.bot_configs WHERE bot_id = $1",
                    bot_id
                )
                logger.info(f"Deleted bot config: {bot_id}")
        except Exception as e:
            logger.error(f"Failed to delete bot config {bot_id}: {e}")
            raise

    # ===================================
    # BOT STATE
    # ===================================

    async def save_bot_state(
        self,
        bot_id: str,
        state_data: Dict[str, Any],
        total_pnl: float,
        win_rate: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        position_side: Optional[str] = None,
        position_size: Optional[float] = None,
        position_entry_price: Optional[float] = None,
        current_trailing_stop: Optional[float] = None,
        peak_equity: Optional[float] = None,
        current_drawdown_pct: Optional[float] = None,
        trading_halted: bool = False,
        halt_reason: Optional[str] = None
    ) -> str:
        """
        Save bot state snapshot for restart resilience

        Returns:
            state_id: UUID of the saved state
        """
        try:
            async with self.pool.acquire() as conn:
                state_id = await conn.fetchval(
                    """
                    SELECT binance.save_bot_state(
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15
                    )
                    """,
                    bot_id,
                    json.dumps(state_data),
                    Decimal(str(total_pnl)),
                    Decimal(str(win_rate)),
                    total_trades,
                    winning_trades,
                    losing_trades,
                    position_side,
                    Decimal(str(position_size)) if position_size else None,
                    Decimal(str(position_entry_price)) if position_entry_price else None,
                    Decimal(str(current_trailing_stop)) if current_trailing_stop is not None else None,
                    Decimal(str(peak_equity)) if peak_equity is not None else None,
                    Decimal(str(current_drawdown_pct)) if current_drawdown_pct is not None else None,
                    trading_halted,
                    halt_reason
                )
                logger.debug(f"Saved bot state: {bot_id}")
                return str(state_id)
        except Exception as e:
            logger.error(f"Failed to save bot state {bot_id}: {e}")
            raise

    async def get_latest_bot_state(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest bot state for restart"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM binance.get_latest_bot_state($1)",
                    bot_id
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get latest bot state {bot_id}: {e}")
            return None

    # ===================================
    # BOT TRADES
    # ===================================

    async def record_trade(
        self,
        bot_id: str,
        symbol: str,
        order_id: str,
        external_order_id: Optional[str],
        side: str,
        order_type: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        commission_asset: str = "USDT",
        pnl: Optional[float] = None,
        strategy_signal: Optional[str] = None,
        signal_reason: Optional[str] = None,
        is_entry: bool = True,
        is_test_mode: bool = True
    ) -> str:
        """
        Record a bot trade

        Returns:
            trade_id: UUID of the recorded trade
        """
        try:
            async with self.pool.acquire() as conn:
                trade_id = await conn.fetchval(
                    """
                    SELECT binance.record_bot_trade(
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                    )
                    """,
                    bot_id,
                    symbol,
                    order_id,
                    external_order_id,
                    side,
                    order_type,
                    Decimal(str(quantity)),
                    Decimal(str(price)),
                    Decimal(str(commission)),
                    commission_asset,
                    Decimal(str(pnl)) if pnl is not None else None,
                    strategy_signal,
                    signal_reason,
                    is_entry,
                    is_test_mode
                )
                logger.info(f"Recorded trade for bot {bot_id}: {side} {quantity} {symbol} @ {price}")
                return str(trade_id)
        except Exception as e:
            logger.error(f"Failed to record trade for bot {bot_id}: {e}")
            raise

    async def get_bot_trades(
        self,
        bot_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get bot trades with pagination"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM binance.bot_trades
                    WHERE bot_id = $1
                    ORDER BY execution_time DESC
                    LIMIT $2 OFFSET $3
                    """,
                    bot_id,
                    limit,
                    offset
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get bot trades {bot_id}: {e}")
            return []

    # ===================================
    # BOT PERFORMANCE
    # ===================================

    async def save_daily_performance_snapshot(
        self,
        bot_id: str,
        snapshot_date: date,
        total_pnl: float,
        daily_pnl: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        win_rate: float,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        profit_factor: Optional[float] = None,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        largest_win: Optional[float] = None,
        largest_loss: Optional[float] = None
    ):
        """Save daily performance snapshot"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO binance.bot_performance_snapshots (
                        bot_id, snapshot_date, total_pnl, daily_pnl, total_trades,
                        winning_trades, losing_trades, win_rate, avg_win, avg_loss,
                        profit_factor, sharpe_ratio, max_drawdown, largest_win, largest_loss
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (bot_id, snapshot_date) DO UPDATE SET
                        total_pnl = EXCLUDED.total_pnl,
                        daily_pnl = EXCLUDED.daily_pnl,
                        total_trades = EXCLUDED.total_trades,
                        winning_trades = EXCLUDED.winning_trades,
                        losing_trades = EXCLUDED.losing_trades,
                        win_rate = EXCLUDED.win_rate,
                        avg_win = EXCLUDED.avg_win,
                        avg_loss = EXCLUDED.avg_loss,
                        profit_factor = EXCLUDED.profit_factor,
                        sharpe_ratio = EXCLUDED.sharpe_ratio,
                        max_drawdown = EXCLUDED.max_drawdown,
                        largest_win = EXCLUDED.largest_win,
                        largest_loss = EXCLUDED.largest_loss
                    """,
                    bot_id,
                    snapshot_date,
                    Decimal(str(total_pnl)),
                    Decimal(str(daily_pnl)),
                    total_trades,
                    winning_trades,
                    losing_trades,
                    Decimal(str(win_rate)),
                    Decimal(str(avg_win)) if avg_win else None,
                    Decimal(str(avg_loss)) if avg_loss else None,
                    Decimal(str(profit_factor)) if profit_factor else None,
                    Decimal(str(sharpe_ratio)) if sharpe_ratio else None,
                    Decimal(str(max_drawdown)) if max_drawdown else None,
                    Decimal(str(largest_win)) if largest_win else None,
                    Decimal(str(largest_loss)) if largest_loss else None
                )
                logger.info(f"Saved daily performance snapshot for bot {bot_id}")
        except Exception as e:
            logger.error(f"Failed to save performance snapshot for bot {bot_id}: {e}")
            raise

    async def get_bot_performance_history(
        self,
        bot_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get bot performance history"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM binance.bot_performance_snapshots
                    WHERE bot_id = $1
                        AND snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY snapshot_date DESC
                    """,
                    bot_id,
                    days
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get performance history for bot {bot_id}: {e}")
            return []

    # ===================================
    # BOT SIGNALS
    # ===================================

    async def record_signal(
        self,
        bot_id: str,
        signal_type: str,
        signal_strength: Optional[float],
        indicators: Dict[str, Any],
        price_at_signal: float,
        action_taken: str,
        rejection_reason: Optional[str] = None,
        trade_id: Optional[str] = None
    ) -> str:
        """Record a bot trading signal"""
        try:
            async with self.pool.acquire() as conn:
                signal_id = await conn.fetchval(
                    """
                    INSERT INTO binance.bot_signals (
                        bot_id, signal_type, signal_strength, indicators,
                        price_at_signal, action_taken, rejection_reason, trade_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING signal_id
                    """,
                    bot_id,
                    signal_type,
                    Decimal(str(signal_strength)) if signal_strength else None,
                    json.dumps(indicators),
                    Decimal(str(price_at_signal)),
                    action_taken,
                    rejection_reason,
                    trade_id
                )
                logger.debug(f"Recorded signal for bot {bot_id}: {signal_type}")
                return str(signal_id)
        except Exception as e:
            logger.error(f"Failed to record signal for bot {bot_id}: {e}")
            raise

    # ===================================
    # VIEWS AND SUMMARIES
    # ===================================

    async def get_bot_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get current bot status from view"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM binance.bot_status_view
                    WHERE bot_id = $1
                    """,
                    bot_id
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get bot status {bot_id}: {e}")
            return None

    async def get_all_bot_statuses(self) -> List[Dict[str, Any]]:
        """Get status for all bots"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM binance.bot_status_view ORDER BY bot_name"
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all bot statuses: {e}")
            return []

    async def get_bot_performance_summary(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get bot performance summary"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM binance.bot_performance_summary
                    WHERE bot_id = $1
                    """,
                    bot_id
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get performance summary for bot {bot_id}: {e}")
            return None

    # ===================================
    # MAINTENANCE
    # ===================================

    async def cleanup_old_metrics(self):
        """Cleanup metrics older than 90 days"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT binance.cleanup_old_metrics()")
                logger.info("Cleaned up old bot metrics")
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
