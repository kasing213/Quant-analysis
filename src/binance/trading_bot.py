"""
Trading Bot Framework
Base classes and interfaces for automated trading strategies
"""

import asyncio
import math
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum
import pandas as pd

from .rest_client import BinanceRESTClient
from .data_manager import BinanceDataManager

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Position:
    """Trading position representation"""

    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop_pct = trailing_stop_pct
        self.highest_price: Optional[float] = entry_price if side == 'BUY' else None
        self.lowest_price: Optional[float] = entry_price if side == 'SELL' else None
        self.trailing_stop_price: Optional[float] = None
        self.entry_time = datetime.now()
        self.exit_price = None
        self.exit_time = None
        self.pnl = 0.0

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate current profit/loss"""
        if self.side == 'BUY':
            self.pnl = (current_price - self.entry_price) * self.quantity
        else:  # SELL (short)
            self.pnl = (self.entry_price - current_price) * self.quantity

        return self.pnl

    def close(self, exit_price: float):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.calculate_pnl(exit_price)

    def update_trailing_stop(self, current_price: float) -> Optional[float]:
        """
        Update trailing stop price based on current market price.

        Returns:
            Updated stop-loss price if trailing stop is active, else None.
        """
        if not self.trailing_stop_pct or self.trailing_stop_pct <= 0:
            return None

        if self.side == 'BUY':
            self.highest_price = max(self.highest_price or current_price, current_price)
            trailing_price = self.highest_price * (1 - self.trailing_stop_pct)
            if self.stop_loss is None or trailing_price > self.stop_loss:
                self.stop_loss = trailing_price
                self.trailing_stop_price = trailing_price
                return trailing_price
        elif self.side == 'SELL':
            self.lowest_price = min(self.lowest_price or current_price, current_price)
            trailing_price = self.lowest_price * (1 + self.trailing_stop_pct)
            if self.stop_loss is None or trailing_price < self.stop_loss:
                self.stop_loss = trailing_price
                self.trailing_stop_price = trailing_price
                return trailing_price

        return self.trailing_stop_price

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'trailing_stop_pct': self.trailing_stop_pct,
            'trailing_stop_price': self.trailing_stop_price,
            'pnl': self.pnl,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None
        }


class TradingStrategy(ABC):
    """
    Abstract base class for trading strategies.
    All custom strategies must inherit from this class.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        Analyze market data and generate trading signal.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading pair symbol

        Returns:
            Dict with keys: 'signal', 'confidence', 'reason'
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict:
        """Return strategy parameters"""
        pass


class TradingBot:
    """
    Base trading bot that executes strategies.

    Features:
    - Strategy execution
    - Position management
    - Risk management (stop-loss, take-profit)
    - Performance tracking
    """

    def __init__(
        self,
        bot_id: str,
        symbol: str,
        strategy: TradingStrategy,
        rest_client: BinanceRESTClient,
        data_manager: BinanceDataManager,
        capital: float = 1000.0,
        risk_per_trade: float = 0.02,  # 2% risk per trade
        max_position_size: float = 0.1,  # 10% of capital per position
        trailing_stop_pct: float = 0.02,
        drawdown_guard_pct: float = 0.15
    ):
        self.bot_id = bot_id
        self.symbol = symbol
        self.strategy = strategy
        self.rest_client = rest_client
        self.data_manager = data_manager
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.trailing_stop_pct = max(trailing_stop_pct, 0.0) if trailing_stop_pct is not None else 0.0
        self.drawdown_guard_pct = max(drawdown_guard_pct, 0.0) if drawdown_guard_pct is not None else 0.0

        self.current_position: Optional[Position] = None
        self.closed_positions: List[Position] = []
        self.running = False
        self.total_pnl = 0.0
        self.peak_equity = capital
        self.current_drawdown_pct = 0.0
        self.trading_halted = False
        self.halt_reason: Optional[str] = None

    async def start(self):
        """Start the trading bot"""
        self.running = True
        logger.info(f"[{self.bot_id}] Bot started for {self.symbol}")

        while self.running:
            try:
                await self._trading_loop()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"[{self.bot_id}] Error in trading loop: {e}")
                await asyncio.sleep(10)

    async def stop(self):
        """Stop the trading bot"""
        self.running = False

        # Close any open positions
        if self.current_position:
            await self.close_position("Bot stopped")

        logger.info(f"[{self.bot_id}] Bot stopped")

    def _update_drawdown(self, unrealized_pnl: float = 0.0) -> None:
        """Recalculate drawdown metrics and enforce drawdown guard."""
        equity = self.capital + self.total_pnl + unrealized_pnl
        self.peak_equity = max(self.peak_equity, equity)

        if self.peak_equity <= 0:
            self.current_drawdown_pct = 0.0
            return

        drawdown = max((self.peak_equity - equity) / self.peak_equity, 0.0)
        self.current_drawdown_pct = drawdown

        if self.drawdown_guard_pct > 0 and drawdown >= self.drawdown_guard_pct:
            if not self.trading_halted:
                self.trading_halted = True
                self.halt_reason = f"drawdown_limit_{drawdown:.2%}"
                logger.warning(
                    f"[{self.bot_id}] Trading halted due to drawdown guard: "
                    f"{drawdown:.2%} drawdown (limit {self.drawdown_guard_pct:.2%})"
                )

    async def _trading_loop(self):
        """Main trading logic"""

        # Get market data
        df = await self.data_manager.get_candles(self.symbol, count=100)

        if df.empty or len(df) < 20:
            logger.debug(f"[{self.bot_id}] Insufficient data")
            return

        # Get current price
        current_price = await self.data_manager.get_latest_price(self.symbol)

        # Check if we have an open position
        if self.current_position:
            await self._manage_position(current_price)
        else:
            if self.trading_halted:
                logger.debug(f"[{self.bot_id}] Trading halted: {self.halt_reason or 'guard active'}")
                return
            # Look for entry signal
            signal = await self.strategy.analyze(df, self.symbol)

            if signal['signal'] == SignalType.BUY.value:
                await self._enter_position(signal, current_price)

    async def _enter_position(self, signal: Dict, current_price: float):
        """Enter a new position"""

        # Calculate position size based on risk
        risk_amount = self.capital * self.risk_per_trade
        max_position_value = self.capital * self.max_position_size

        # Calculate quantity
        quantity = min(risk_amount / current_price, max_position_value / current_price)

        # Round to appropriate precision (would need symbol info for exact precision)
        quantity = round(quantity, 6)

        # Calculate stop-loss (example: 2% below entry)
        stop_loss = current_price * 0.98

        # Calculate take-profit (example: 4% above entry for 2:1 risk/reward)
        take_profit = current_price * 1.04

        logger.info(f"[{self.bot_id}] ENTERING POSITION:")
        logger.info(f"  Symbol: {self.symbol}")
        logger.info(f"  Price: ${current_price:.2f}")
        logger.info(f"  Quantity: {quantity}")
        logger.info(f"  Stop Loss: ${stop_loss:.2f}")
        logger.info(f"  Take Profit: ${take_profit:.2f}")
        logger.info(f"  Reason: {signal.get('reason', 'N/A')}")
        if self.trailing_stop_pct > 0:
            logger.info(f"  Trailing Stop: {self.trailing_stop_pct:.2%} below peak")

        # Execute order
        try:
            order = await self.rest_client.create_market_order(
                symbol=self.symbol,
                side='BUY',
                quantity=quantity
            )

            # Create position
            self.current_position = Position(
                symbol=self.symbol,
                side='BUY',
                quantity=quantity,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop_pct=self.trailing_stop_pct if self.trailing_stop_pct > 0 else None
            )

            if self.trailing_stop_pct > 0:
                self.current_position.update_trailing_stop(current_price)

            logger.info(f"[{self.bot_id}] Position opened: {order}")

        except Exception as e:
            logger.error(f"[{self.bot_id}] Failed to enter position: {e}")

    async def _manage_position(self, current_price: float):
        """Manage existing position (check stop-loss, take-profit)"""

        if not self.current_position:
            return

        # Calculate current PnL
        pnl = self.current_position.calculate_pnl(current_price)
        pnl_percent = (pnl / (self.current_position.entry_price * self.current_position.quantity)) * 100

        logger.debug(f"[{self.bot_id}] Position PnL: ${pnl:.2f} ({pnl_percent:.2f}%)")

        if self.current_position.trailing_stop_pct:
            updated_stop = self.current_position.update_trailing_stop(current_price)
            if updated_stop:
                logger.debug(
                    f"[{self.bot_id}] Trailing stop updated to ${updated_stop:.2f} "
                    f"(peak ${self.current_position.highest_price:.2f})"
                )

        self._update_drawdown(unrealized_pnl=pnl)

        # Check stop-loss
        stop_loss = self.current_position.stop_loss
        if stop_loss and current_price <= stop_loss:
            reason = (
                f"Trailing stop hit at ${current_price:.2f}"
                if self.current_position.trailing_stop_price
                and math.isclose(stop_loss, self.current_position.trailing_stop_price, rel_tol=1e-4, abs_tol=1e-6)
                else f"Stop-loss hit at ${current_price:.2f}"
            )
            await self.close_position(reason)
            return

        # Check take-profit
        if self.current_position.take_profit and current_price >= self.current_position.take_profit:
            await self.close_position(f"Take-profit hit at ${current_price:.2f}")
            return

    async def close_position(self, reason: str):
        """Close current position"""

        if not self.current_position:
            return

        current_price = await self.data_manager.get_latest_price(self.symbol)

        logger.info(f"[{self.bot_id}] CLOSING POSITION:")
        logger.info(f"  Reason: {reason}")
        logger.info(f"  Exit Price: ${current_price:.2f}")

        try:
            # Execute sell order
            order = await self.rest_client.create_market_order(
                symbol=self.symbol,
                side='SELL',
                quantity=self.current_position.quantity
            )

            # Close position
            self.current_position.close(current_price)

            # Update stats
            self.total_pnl += self.current_position.pnl
            self.closed_positions.append(self.current_position)
            self._update_drawdown()

            logger.info(f"[{self.bot_id}] Position closed: PnL = ${self.current_position.pnl:.2f}")
            logger.info(f"[{self.bot_id}] Total PnL: ${self.total_pnl:.2f}")
            if self.trading_halted:
                logger.info(
                    f"[{self.bot_id}] Bot remains halted (reason: {self.halt_reason})"
                )
            # Clear current position
            self.current_position = None

        except Exception as e:
            logger.error(f"[{self.bot_id}] Failed to close position: {e}")

    def get_stats(self) -> Dict:
        """Get bot performance statistics"""

        total_trades = len(self.closed_positions)
        winning_trades = sum(1 for p in self.closed_positions if p.pnl > 0)
        losing_trades = total_trades - winning_trades

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            'bot_id': self.bot_id,
            'symbol': self.symbol,
            'strategy': self.strategy.name,
            'capital': self.capital,
            'total_pnl': self.total_pnl,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'current_position': self.current_position.to_dict() if self.current_position else None,
            'running': self.running,
            'max_position_size': self.max_position_size,
            'trailing_stop_pct': self.trailing_stop_pct if self.trailing_stop_pct > 0 else None,
            'drawdown_guard_pct': self.drawdown_guard_pct if self.drawdown_guard_pct > 0 else None,
            'current_drawdown_pct': self.current_drawdown_pct,
            'trading_halted': self.trading_halted,
            'halt_reason': self.halt_reason
        }
