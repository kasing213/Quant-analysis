"""
Bot Management API Endpoints
FastAPI router for controlling trading bots
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics (optional)
try:
    from ..metrics import (
        ACTIVE_BOTS,
        BOT_TRADES_TOTAL,
        BOT_PNL,
        update_bot_metrics,
        record_trade
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.debug("Metrics module not available")

router = APIRouter(prefix="/bots", tags=["bots"])

# Global orchestrator instance (initialized in main.py)
_orchestrator = None
_persistence = None


def set_orchestrator(orchestrator):
    """Set global orchestrator instance"""
    global _orchestrator
    _orchestrator = orchestrator


def set_persistence(persistence):
    """Set global persistence instance"""
    global _persistence
    _persistence = persistence


# Pydantic models
class BotCreateRequest(BaseModel):
    bot_id: str
    symbol: str
    strategy_name: str
    strategy_params: Optional[Dict] = None
    capital: float = 1000.0
    risk_per_trade: float = 0.02
    max_position_size: float = 0.1
    trailing_stop_pct: Optional[float] = 0.02
    drawdown_guard_pct: Optional[float] = 0.15
    auto_start: bool = False


class BotResponse(BaseModel):
    bot_id: str
    symbol: str
    strategy: str
    capital: float
    total_pnl: float
    total_trades: int
    win_rate: float
    max_position_size: float
    trailing_stop_pct: Optional[float] = None
    drawdown_guard_pct: Optional[float] = None
    current_drawdown_pct: float
    trading_halted: bool
    halt_reason: Optional[str] = None
    running: bool
    current_position: Optional[Dict] = None


class PortfolioResponse(BaseModel):
    total_bots: int
    total_capital: float
    total_pnl: float
    total_pnl_percent: float
    total_trades: int
    winning_trades: int
    win_rate: float
    timestamp: str


@router.post("/create", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(request: BotCreateRequest):
    """
    Create a new trading bot.

    - **bot_id**: Unique identifier for the bot
    - **symbol**: Trading pair (e.g., 'BTCUSDT')
    - **strategy_name**: Strategy to use (e.g., 'RSI_14')
    - **strategy_params**: Strategy parameters (optional)
    - **capital**: Initial capital (default: 1000)
    - **risk_per_trade**: Risk per trade as decimal (default: 0.02)
    - **auto_start**: Auto-start the bot (default: false)
    """

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        # Create strategy instance based on name
        from ...binance.strategies.rsi_strategy import RSIStrategy
        from ...binance.strategies.macd_strategy import MACDStrategy
        from ...binance.strategies.mean_reversion_strategy import MeanReversionStrategy

        params = request.strategy_params or {}
        strategy_name = request.strategy_name.upper()

        if strategy_name.startswith('RSI'):
            strategy = RSIStrategy(
                period=int(params.get('period', 14)),
                oversold=float(params.get('oversold', 30)),
                overbought=float(params.get('overbought', 70)),
                min_confidence=float(params.get('min_confidence', 0.6))
            )
        elif strategy_name.startswith('MACD'):
            fast = int(params.get('fast_period', params.get('fast', 12)))
            slow = int(params.get('slow_period', params.get('slow', 26)))
            signal = int(params.get('signal_period', params.get('signal', 9)))

            parts = strategy_name.split('_')
            if len(parts) >= 4:
                try:
                    fast = int(parts[1])
                    slow = int(parts[2])
                    signal = int(parts[3])
                except (ValueError, IndexError):
                    pass

            strategy = MACDStrategy(
                fast_period=fast,
                slow_period=slow,
                signal_period=signal,
                min_confidence=float(params.get('min_confidence', 0.55))
            )
        elif strategy_name.startswith('MEAN_REVERSION') or strategy_name.startswith('MEANREV'):
            lookback = int(params.get('lookback_window', params.get('lookback', 20)))
            threshold = float(params.get('z_threshold', params.get('threshold', 1.5)))
            exit_threshold = float(params.get('exit_threshold', 0.5))

            strategy = MeanReversionStrategy(
                lookback_window=lookback,
                zscore_threshold=threshold,
                exit_threshold=exit_threshold,
                min_confidence=float(params.get('min_confidence', 0.55))
            )
        else:
            raise ValueError(f"Unknown strategy: {request.strategy_name}")

        # Create bot
        bot = await _orchestrator.create_bot(
            bot_id=request.bot_id,
            symbol=request.symbol,
            strategy=strategy,
            capital=request.capital,
            risk_per_trade=request.risk_per_trade,
            max_position_size=request.max_position_size,
            trailing_stop_pct=request.trailing_stop_pct,
            drawdown_guard_pct=request.drawdown_guard_pct,
            auto_start=request.auto_start
        )

        stats = bot.get_stats()
        return BotResponse(**stats)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot: {str(e)}"
        )


@router.post("/{bot_id}/start", status_code=status.HTTP_200_OK)
async def start_bot(bot_id: str):
    """Start a specific bot"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        await _orchestrator.start_bot(bot_id)
        return {"message": f"Bot {bot_id} started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{bot_id}/stop", status_code=status.HTTP_200_OK)
async def stop_bot(bot_id: str):
    """Stop a specific bot"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        await _orchestrator.stop_bot(bot_id)
        return {"message": f"Bot {bot_id} stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{bot_id}", status_code=status.HTTP_200_OK)
async def remove_bot(bot_id: str):
    """Remove a bot (stops it first if running)"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        await _orchestrator.remove_bot(bot_id)
        return {"message": f"Bot {bot_id} removed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{bot_id}/stats", response_model=BotResponse)
async def get_bot_stats(bot_id: str):
    """Get statistics for a specific bot"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        stats = _orchestrator.get_bot_stats(bot_id)
        return BotResponse(**stats)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get bot stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=Dict)
async def get_all_bots():
    """Get all bots and their statistics"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        stats = _orchestrator.get_all_stats()

        # Update Prometheus metrics
        if METRICS_AVAILABLE and 'bots' in stats:
            running_count = sum(1 for bot in stats['bots'] if bot.get('running', False))
            stopped_count = sum(1 for bot in stats['bots'] if not bot.get('running', False))

            ACTIVE_BOTS.labels(status="running").set(running_count)
            ACTIVE_BOTS.labels(status="stopped").set(stopped_count)

            # Update P&L for each bot
            for bot in stats['bots']:
                bot_id = bot.get('bot_id', 'unknown')
                symbol = bot.get('symbol', 'unknown')
                pnl = bot.get('total_pnl', 0.0)
                BOT_PNL.labels(bot_id=bot_id, symbol=symbol).set(pnl)

        return stats
    except Exception as e:
        logger.error(f"Failed to get all bot stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/portfolio/summary", response_model=PortfolioResponse)
async def get_portfolio_summary():
    """Get overall portfolio summary"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        summary = _orchestrator.get_portfolio_summary()
        return PortfolioResponse(**summary)
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/start-all", status_code=status.HTTP_200_OK)
async def start_all_bots():
    """Start all bots"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        await _orchestrator.start_all_bots()
        return {"message": "All bots started successfully"}
    except Exception as e:
        logger.error(f"Failed to start all bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/stop-all", status_code=status.HTTP_200_OK)
async def stop_all_bots():
    """Stop all bots"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        await _orchestrator.stop_all_bots()
        return {"message": "All bots stopped successfully"}
    except Exception as e:
        logger.error(f"Failed to stop all bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Check health of bot orchestrator and all components"""

    if not _orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot orchestrator not initialized"
        )

    try:
        health = await _orchestrator.health_check()
        return health
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ===================================
# PERSISTENCE-BACKED ENDPOINTS
# ===================================

@router.get("/{bot_id}/trades", status_code=status.HTTP_200_OK)
async def get_bot_trades(bot_id: str, limit: int = 100, offset: int = 0):
    """Get trade history for a specific bot from persistence"""

    if not _persistence:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot persistence not enabled"
        )

    try:
        trades = await _persistence.get_bot_trades(bot_id, limit=limit, offset=offset)
        return {"bot_id": bot_id, "trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"Failed to get bot trades: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{bot_id}/performance", status_code=status.HTTP_200_OK)
async def get_bot_performance(bot_id: str, days: int = 30):
    """Get performance history for a specific bot"""

    if not _persistence:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot persistence not enabled"
        )

    try:
        performance = await _persistence.get_bot_performance_history(bot_id, days=days)
        return {"bot_id": bot_id, "performance": performance, "days": days}
    except Exception as e:
        logger.error(f"Failed to get bot performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{bot_id}/status", status_code=status.HTTP_200_OK)
async def get_bot_status_detailed(bot_id: str):
    """Get detailed bot status including persisted data"""

    if not _persistence:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot persistence not enabled"
        )

    try:
        status_data = await _persistence.get_bot_status(bot_id)
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot {bot_id} not found in persistence"
            )
        return status_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bot status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/persistence/all-bots", status_code=status.HTTP_200_OK)
async def get_all_persisted_bots():
    """Get all bots from persistence (including inactive)"""

    if not _persistence:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot persistence not enabled"
        )

    try:
        bots = await _persistence.get_all_bot_statuses()
        return {"bots": bots, "count": len(bots)}
    except Exception as e:
        logger.error(f"Failed to get all persisted bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
