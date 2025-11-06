"""
Bot Orchestrator
Manages multiple trading bots and coordinates their execution
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, date
from .trading_bot import TradingBot, TradingStrategy
from .rest_client import BinanceRESTClient
from .data_manager import BinanceDataManager
from .bot_persistence import BotPersistence

logger = logging.getLogger(__name__)


class BotOrchestrator:
    """
    Orchestrates multiple trading bots.

    Features:
    - Manage multiple bots for different symbols
    - Start/stop individual bots
    - Monitor bot performance
    - Shared data manager for efficient data streaming
    - Centralized risk management
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        testnet: bool = True,
        test_mode: bool = True,
        enable_persistence: bool = True
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.test_mode = test_mode
        self.enable_persistence = enable_persistence

        # Shared components
        self.data_manager = BinanceDataManager(
            redis_host=redis_host,
            redis_port=redis_port,
            testnet=testnet
        )
        self.rest_client = None
        self.persistence = BotPersistence() if enable_persistence else None

        # Bot management
        self.bots: Dict[str, TradingBot] = {}
        self.bot_tasks: Dict[str, asyncio.Task] = {}
        self.running = False

    async def initialize(self):
        """Initialize orchestrator and shared resources"""
        logger.info("Initializing Bot Orchestrator...")

        # Initialize persistence layer
        if self.persistence:
            try:
                await self.persistence.initialize()
                logger.info("Bot persistence initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize persistence: {e}. Continuing without persistence.")
                self.persistence = None

        # Connect data manager
        await self.data_manager.connect()

        # Initialize REST client
        self.rest_client = BinanceRESTClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
            test_mode=self.test_mode
        )
        await self.rest_client.__aenter__()

        # Start data streaming
        self.streaming_task = asyncio.create_task(self.data_manager.start_streaming())

        # Restore bots from persistence
        if self.persistence:
            await self._restore_bots_from_persistence()

        logger.info("Bot Orchestrator initialized successfully")

    async def create_bot(
        self,
        bot_id: str,
        symbol: str,
        strategy: TradingStrategy,
        capital: float = 1000.0,
        risk_per_trade: float = 0.02,
        max_position_size: float = 0.1,
        trailing_stop_pct: Optional[float] = 0.02,
        drawdown_guard_pct: Optional[float] = 0.15,
        auto_start: bool = False
    ) -> TradingBot:
        """
        Create a new trading bot.

        Args:
            bot_id: Unique identifier for the bot
            symbol: Trading pair (e.g., 'BTCUSDT')
            strategy: Trading strategy instance
            capital: Initial capital for the bot
            risk_per_trade: Risk percentage per trade (default 2%)
            max_position_size: Maximum capital allocation per position (default 10%)
            trailing_stop_pct: Percentage distance for trailing stop (None/0 disables)
            drawdown_guard_pct: Maximum allowable drawdown before halting trading
            auto_start: Auto-start the bot after creation

        Returns:
            TradingBot instance
        """

        if bot_id in self.bots:
            raise ValueError(f"Bot {bot_id} already exists")

        # Subscribe to symbol data if not already subscribed
        await self.data_manager.subscribe_symbol(symbol, interval='1m')

        # Create bot
        bot = TradingBot(
            bot_id=bot_id,
            symbol=symbol,
            strategy=strategy,
            rest_client=self.rest_client,
            data_manager=self.data_manager,
            capital=capital,
            risk_per_trade=risk_per_trade,
            max_position_size=max_position_size,
            trailing_stop_pct=trailing_stop_pct,
            drawdown_guard_pct=drawdown_guard_pct
        )

        self.bots[bot_id] = bot

        # Persist bot configuration
        if self.persistence:
            try:
                await self.persistence.save_bot_config(
                    bot_id=bot_id,
                    bot_name=bot_id,
                    symbol=symbol,
                    strategy_name=strategy.name,
                    strategy_params=strategy.get_params() if hasattr(strategy, 'get_params') else {},
                    capital=capital,
                    position_size=capital * max_position_size,
                    risk_per_trade=risk_per_trade,
                    max_position_size=max_position_size,
                    trailing_stop_pct=trailing_stop_pct,
                    drawdown_guard_pct=drawdown_guard_pct
                )
                logger.info(f"Bot configuration persisted: {bot_id}")
            except Exception as e:
                logger.error(f"Failed to persist bot config: {e}")

        logger.info(f"Bot created: {bot_id} ({symbol}) - Strategy: {strategy.name}")

        if auto_start:
            await self.start_bot(bot_id)

        return bot

    async def start_bot(self, bot_id: str):
        """Start a specific bot"""

        if bot_id not in self.bots:
            raise ValueError(f"Bot {bot_id} not found")

        if bot_id in self.bot_tasks and not self.bot_tasks[bot_id].done():
            logger.warning(f"Bot {bot_id} is already running")
            return

        bot = self.bots[bot_id]
        self.bot_tasks[bot_id] = asyncio.create_task(bot.start())

        # Update bot status in persistence
        if self.persistence:
            try:
                await self.persistence.update_bot_status(bot_id, is_running=True)
            except Exception as e:
                logger.error(f"Failed to persist bot start status: {e}")

        logger.info(f"Bot {bot_id} started")

    async def stop_bot(self, bot_id: str):
        """Stop a specific bot"""

        if bot_id not in self.bots:
            raise ValueError(f"Bot {bot_id} not found")

        bot = self.bots[bot_id]

        # Save bot state before stopping
        if self.persistence:
            try:
                await self._persist_bot_state(bot_id)
            except Exception as e:
                logger.error(f"Failed to persist bot state before stopping: {e}")

        await bot.stop()

        if bot_id in self.bot_tasks:
            self.bot_tasks[bot_id].cancel()
            try:
                await self.bot_tasks[bot_id]
            except asyncio.CancelledError:
                pass
            del self.bot_tasks[bot_id]

        # Update bot status in persistence
        if self.persistence:
            try:
                await self.persistence.update_bot_status(bot_id, is_running=False)
            except Exception as e:
                logger.error(f"Failed to persist bot stop status: {e}")

        logger.info(f"Bot {bot_id} stopped")

    async def remove_bot(self, bot_id: str):
        """Remove a bot (stops it first if running)"""

        if bot_id in self.bot_tasks:
            await self.stop_bot(bot_id)

        if bot_id in self.bots:
            del self.bots[bot_id]

            # Mark bot as inactive in persistence (don't delete to preserve history)
            if self.persistence:
                try:
                    await self.persistence.update_bot_status(bot_id, is_active=False, is_running=False)
                except Exception as e:
                    logger.error(f"Failed to persist bot removal: {e}")

            logger.info(f"Bot {bot_id} removed")

    async def start_all_bots(self):
        """Start all bots"""
        for bot_id in self.bots:
            await self.start_bot(bot_id)

    async def stop_all_bots(self):
        """Stop all bots"""
        for bot_id in list(self.bot_tasks.keys()):
            await self.stop_bot(bot_id)

    def get_bot_stats(self, bot_id: str) -> Dict:
        """Get statistics for a specific bot"""

        if bot_id not in self.bots:
            raise ValueError(f"Bot {bot_id} not found")

        return self.bots[bot_id].get_stats()

    def get_all_stats(self) -> Dict:
        """Get statistics for all bots"""

        stats = {
            'orchestrator': {
                'total_bots': len(self.bots),
                'running_bots': len([b for b in self.bots.values() if b.running]),
                'testnet': self.testnet,
                'test_mode': self.test_mode
            },
            'bots': {}
        }

        for bot_id, bot in self.bots.items():
            stats['bots'][bot_id] = bot.get_stats()

        return stats

    def get_portfolio_summary(self) -> Dict:
        """Get overall portfolio summary"""

        total_capital = sum(bot.capital for bot in self.bots.values())
        total_pnl = sum(bot.total_pnl for bot in self.bots.values())

        all_trades = []
        for bot in self.bots.values():
            all_trades.extend(bot.closed_positions)

        winning_trades = sum(1 for p in all_trades if p.pnl > 0)
        total_trades = len(all_trades)

        return {
            'total_bots': len(self.bots),
            'total_capital': total_capital,
            'total_pnl': total_pnl,
            'total_pnl_percent': (total_pnl / total_capital * 100) if total_capital > 0 else 0,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }

    async def health_check(self) -> Dict:
        """Check health of orchestrator and all components"""

        # Check data manager health
        data_health = await self.data_manager.health_check()

        # Check bot health
        bot_health = {}
        for bot_id, bot in self.bots.items():
            bot_health[bot_id] = {
                'running': bot.running,
                'has_position': bot.current_position is not None,
                'total_pnl': bot.total_pnl
            }

        return {
            'data_manager': data_health,
            'bots': bot_health,
            'persistence_enabled': self.persistence is not None,
            'timestamp': datetime.now().isoformat()
        }

    async def _persist_bot_state(self, bot_id: str):
        """Persist current state of a bot"""
        if not self.persistence or bot_id not in self.bots:
            return

        bot = self.bots[bot_id]
        stats = bot.get_stats()

        try:
            await self.persistence.save_bot_state(
                bot_id=bot_id,
                state_data={
                    'symbol': bot.symbol,
                    'strategy': bot.strategy.name,
                    'capital': bot.capital
                },
                total_pnl=stats.get('total_pnl', 0.0),
                win_rate=stats.get('win_rate', 0.0),
                total_trades=stats.get('total_trades', 0),
                winning_trades=stats.get('winning_trades', 0),
                losing_trades=stats.get('losing_trades', 0),
                position_side=stats.get('current_position', {}).get('side') if stats.get('current_position') else None,
                position_size=stats.get('current_position', {}).get('size') if stats.get('current_position') else None,
                position_entry_price=stats.get('current_position', {}).get('entry_price') if stats.get('current_position') else None,
                current_trailing_stop=bot.current_trailing_stop if hasattr(bot, 'current_trailing_stop') else None,
                peak_equity=bot.peak_equity if hasattr(bot, 'peak_equity') else None,
                current_drawdown_pct=stats.get('current_drawdown_pct', 0.0),
                trading_halted=stats.get('trading_halted', False),
                halt_reason=stats.get('halt_reason')
            )
            logger.debug(f"Persisted state for bot {bot_id}")
        except Exception as e:
            logger.error(f"Failed to persist bot state for {bot_id}: {e}")

    async def _restore_bots_from_persistence(self):
        """Restore bots from persistence on startup"""
        if not self.persistence:
            return

        try:
            configs = await self.persistence.get_all_bot_configs(active_only=True)
            logger.info(f"Found {len(configs)} bot configurations to restore")

            for config in configs:
                bot_id = config['bot_id']

                # Skip if bot already exists (manual creation takes precedence)
                if bot_id in self.bots:
                    logger.info(f"Bot {bot_id} already exists, skipping restoration")
                    continue

                try:
                    # Get strategy from config
                    strategy_name = config['strategy_name']
                    strategy_params = config.get('strategy_params', {})
                    if isinstance(strategy_params, str):
                        import json
                        strategy_params = json.loads(strategy_params)

                    # Create strategy instance
                    strategy = self._create_strategy_from_config(strategy_name, strategy_params)
                    if not strategy:
                        logger.warning(f"Unknown strategy {strategy_name} for bot {bot_id}, skipping")
                        continue

                    # Create bot
                    await self.create_bot(
                        bot_id=bot_id,
                        symbol=config['symbol'],
                        strategy=strategy,
                        capital=float(config['capital']),
                        risk_per_trade=float(config['risk_per_trade']),
                        max_position_size=float(config['max_position_size']),
                        trailing_stop_pct=float(config['trailing_stop_pct']) if config.get('trailing_stop_pct') else None,
                        drawdown_guard_pct=float(config['drawdown_guard_pct']) if config.get('drawdown_guard_pct') else None,
                        auto_start=config.get('is_running', False)
                    )

                    logger.info(f"Restored bot: {bot_id}")

                except Exception as e:
                    logger.error(f"Failed to restore bot {bot_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to restore bots from persistence: {e}")

    def _create_strategy_from_config(self, strategy_name: str, params: Dict):
        """Create a strategy instance from configuration"""
        try:
            from .strategies.rsi_strategy import RSIStrategy
            from .strategies.macd_strategy import MACDStrategy
            from .strategies.mean_reversion_strategy import MeanReversionStrategy

            strategy_name_upper = strategy_name.upper()

            if 'RSI' in strategy_name_upper:
                return RSIStrategy(
                    period=int(params.get('period', 14)),
                    oversold=float(params.get('oversold', 30)),
                    overbought=float(params.get('overbought', 70)),
                    min_confidence=float(params.get('min_confidence', 0.6))
                )
            elif 'MACD' in strategy_name_upper:
                return MACDStrategy(
                    fast_period=int(params.get('fast_period', params.get('fast', 12))),
                    slow_period=int(params.get('slow_period', params.get('slow', 26))),
                    signal_period=int(params.get('signal_period', params.get('signal', 9))),
                    min_confidence=float(params.get('min_confidence', 0.55))
                )
            elif 'MEAN_REVERSION' in strategy_name_upper or 'MEANREV' in strategy_name_upper:
                return MeanReversionStrategy(
                    lookback_window=int(params.get('lookback_window', params.get('lookback', 20))),
                    zscore_threshold=float(params.get('zscore_threshold', params.get('threshold', 1.5))),
                    exit_threshold=float(params.get('exit_threshold', 0.5)),
                    min_confidence=float(params.get('min_confidence', 0.55))
                )
            else:
                return None
        except Exception as e:
            logger.error(f"Failed to create strategy {strategy_name}: {e}")
            return None

    async def shutdown(self):
        """Gracefully shutdown orchestrator"""

        logger.info("Shutting down Bot Orchestrator...")

        # Save state for all running bots
        if self.persistence:
            for bot_id in self.bots:
                try:
                    await self._persist_bot_state(bot_id)
                except Exception as e:
                    logger.error(f"Failed to save state for bot {bot_id} during shutdown: {e}")

        # Stop all bots
        await self.stop_all_bots()

        # Cancel streaming task
        if hasattr(self, 'streaming_task'):
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass

        # Close connections
        await self.data_manager.close()

        if self.rest_client:
            await self.rest_client.__aexit__(None, None, None)

        # Close persistence
        if self.persistence:
            await self.persistence.close()

        logger.info("Bot Orchestrator shut down successfully")


# Example usage
async def example():
    """Example of using the bot orchestrator"""

    from .strategies.rsi_strategy import RSIStrategy

    # Create orchestrator
    orchestrator = BotOrchestrator(
        api_key="your_api_key",
        api_secret="your_api_secret",
        testnet=True,
        test_mode=True
    )

    # Initialize
    await orchestrator.initialize()

    # Create bots with different strategies
    rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)

    # Bot 1: BTC with RSI
    await orchestrator.create_bot(
        bot_id="btc_rsi",
        symbol="BTCUSDT",
        strategy=rsi_strategy,
        capital=1000.0,
        auto_start=True
    )

    # Bot 2: ETH with RSI
    await orchestrator.create_bot(
        bot_id="eth_rsi",
        symbol="ETHUSDT",
        strategy=rsi_strategy,
        capital=500.0,
        auto_start=True
    )

    # Monitor for 60 seconds
    for i in range(12):
        await asyncio.sleep(5)

        # Get stats
        stats = orchestrator.get_all_stats()
        print(f"\n--- Stats Update {i+1} ---")
        print(f"Total Bots: {stats['orchestrator']['total_bots']}")
        print(f"Running Bots: {stats['orchestrator']['running_bots']}")

        for bot_id, bot_stats in stats['bots'].items():
            print(f"\n{bot_id}:")
            print(f"  Total PnL: ${bot_stats['total_pnl']:.2f}")
            print(f"  Trades: {bot_stats['total_trades']}")
            print(f"  Win Rate: {bot_stats['win_rate']:.2f}%")

    # Shutdown
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(example())
