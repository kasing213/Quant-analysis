import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from ..database import get_async_db
from ..models import PortfolioSummary
from ..schemas import PortfolioSummary as PortfolioSummarySchema, PortfolioSummaryCreate
from ..mock_data import (
    fixtures_enabled,
    get_mock_portfolio_summary,
    get_mock_portfolio_history,
)
from src.core.risk_manager import RiskManager, RiskCalculator, RiskMetrics

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
logger = logging.getLogger(__name__)

# Prometheus metrics (optional)
try:
    from ..metrics import (
        PORTFOLIO_VALUE,
        PORTFOLIO_CASH,
        PORTFOLIO_POSITIONS,
        update_portfolio_metrics
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.debug("Metrics module not available")

# Global instances (initialized in main.py)
_risk_manager: Optional[RiskManager] = None
_bot_orchestrator = None


def set_risk_manager(risk_manager: RiskManager):
    """Set global risk manager instance"""
    global _risk_manager
    _risk_manager = risk_manager


def get_risk_manager() -> Optional[RiskManager]:
    """Get risk manager instance"""
    return _risk_manager


def set_bot_orchestrator(orchestrator):
    """Set global bot orchestrator instance"""
    global _bot_orchestrator
    _bot_orchestrator = orchestrator


def get_bot_orchestrator():
    """Get bot orchestrator instance"""
    return _bot_orchestrator

@router.get("/summary", response_model=PortfolioSummarySchema)
async def get_portfolio_summary(db: AsyncSession = Depends(get_async_db)):
    """Get the latest portfolio summary"""
    summary = None
    try:
        stmt = select(PortfolioSummary).order_by(desc(PortfolioSummary.timestamp))
        result = await db.execute(stmt)
        summary = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("Portfolio summary query failed, falling back to fixtures: %s", exc)

    if summary:
        return summary

    if fixtures_enabled():
        return PortfolioSummarySchema(**get_mock_portfolio_summary())

    raise HTTPException(status_code=404, detail="No portfolio summary found")

@router.get("/summary/history", response_model=List[PortfolioSummarySchema])
async def get_portfolio_history(limit: int = 100, db: AsyncSession = Depends(get_async_db)):
    """Get portfolio summary history"""
    summaries = []
    try:
        stmt = select(PortfolioSummary).order_by(desc(PortfolioSummary.timestamp)).limit(limit)
        result = await db.execute(stmt)
        summaries = result.scalars().all()
    except Exception as exc:
        logger.warning("Portfolio history query failed, falling back to fixtures: %s", exc)

    if summaries:
        return summaries

    if fixtures_enabled():
        history = get_mock_portfolio_history(samples=min(limit, 14))
        return [PortfolioSummarySchema(**item) for item in history][:limit]

    return []

@router.post("/summary", response_model=PortfolioSummarySchema)
async def create_portfolio_summary(summary: PortfolioSummaryCreate, db: AsyncSession = Depends(get_async_db)):
    """Create a new portfolio summary snapshot"""
    db_summary = PortfolioSummary(**summary.model_dump())
    db.add(db_summary)
    await db.flush()
    await db.refresh(db_summary)
    return db_summary


# ===================================
# LIVE BINANCE BOT PORTFOLIO
# ===================================

@router.get("/live/summary")
async def get_live_portfolio_summary() -> Dict[str, Any]:
    """
    Get live portfolio summary from running Binance bots

    This endpoint provides real-time portfolio data from active trading bots
    instead of historical database records. Requires bot orchestrator to be running.
    """
    orchestrator = get_bot_orchestrator()

    if not orchestrator:
        return {
            "status": "unavailable",
            "message": "Bot orchestrator not initialized. Enable bots with BINANCE_ENABLE_BOTS=true",
            "total_bots": 0,
            "total_capital": 0,
            "total_pnl": 0
        }

    try:
        # Get live portfolio data from bot orchestrator
        portfolio_summary = orchestrator.get_portfolio_summary()

        # Update Prometheus metrics
        if METRICS_AVAILABLE:
            update_portfolio_metrics({
                'total_value': portfolio_summary['total_capital'] + portfolio_summary['total_pnl'],
                'cash_balance': portfolio_summary['total_capital']
            })

        return {
            "status": "live",
            "data_source": "binance_bots",
            "total_bots": portfolio_summary['total_bots'],
            "total_capital": portfolio_summary['total_capital'],
            "total_pnl": portfolio_summary['total_pnl'],
            "total_pnl_percent": portfolio_summary['total_pnl_percent'],
            "total_trades": portfolio_summary['total_trades'],
            "winning_trades": portfolio_summary['winning_trades'],
            "win_rate": portfolio_summary['win_rate'],
            "timestamp": portfolio_summary['timestamp']
        }

    except Exception as e:
        logger.error(f"Error getting live portfolio summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving live portfolio data: {str(e)}"
        )


@router.get("/live/bots")
async def get_live_bot_details() -> Dict[str, Any]:
    """
    Get detailed information about all running bots

    Returns individual bot statistics, positions, and performance metrics
    """
    orchestrator = get_bot_orchestrator()

    if not orchestrator:
        return {
            "status": "unavailable",
            "message": "Bot orchestrator not initialized",
            "bots": {}
        }

    try:
        # Get all bot stats
        all_stats = orchestrator.get_all_stats()

        return {
            "status": "live",
            "data_source": "binance_bots",
            "orchestrator": all_stats['orchestrator'],
            "bots": all_stats['bots'],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting live bot details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving bot details: {str(e)}"
        )


@router.get("/live/bot/{bot_id}")
async def get_live_bot_stats(bot_id: str) -> Dict[str, Any]:
    """
    Get detailed statistics for a specific bot

    Returns real-time performance metrics, positions, and trading history
    """
    orchestrator = get_bot_orchestrator()

    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Bot orchestrator not initialized"
        )

    try:
        # Get bot stats
        bot_stats = orchestrator.get_bot_stats(bot_id)

        return {
            "status": "live",
            "data_source": "binance_bot",
            "bot_id": bot_id,
            "stats": bot_stats,
            "timestamp": datetime.now().isoformat()
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting bot stats for {bot_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving bot stats: {str(e)}"
        )


# ===================================
# RISK ANALYTICS ENDPOINTS
# ===================================

@router.get("/analytics/risk-metrics")
async def get_risk_metrics(
    days: int = 30,
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get comprehensive risk metrics for the portfolio

    Calculates:
    - VaR (95% and 99%)
    - CVaR (Conditional VaR)
    - Sharpe Ratio
    - Sortino Ratio
    - Calmar Ratio
    - Volatility metrics
    - Drawdown analysis
    """
    try:
        # Get historical portfolio data
        stmt = select(PortfolioSummary).order_by(
            desc(PortfolioSummary.timestamp)
        ).limit(days)
        result = await db.execute(stmt)
        summaries = result.scalars().all()

        if not summaries:
            # Return mock data if no historical data available
            return _generate_mock_risk_metrics()

        # Convert to pandas for analysis
        df = pd.DataFrame([{
            'timestamp': s.timestamp,
            'total_value': s.total_value,
            'cash_balance': s.cash_balance,
            'total_pnl': s.total_pnl
        } for s in summaries])

        df = df.sort_values('timestamp')

        # Calculate returns
        df['returns'] = df['total_value'].pct_change()
        returns = df['returns'].dropna()

        # Calculate equity curve
        equity_curve = df['total_value']

        # Calculate risk metrics
        metrics = RiskMetrics()

        if len(returns) > 5:  # Need minimum data points
            metrics.var_95 = float(RiskCalculator.calculate_var(returns, 0.95))
            metrics.var_99 = float(RiskCalculator.calculate_var(returns, 0.99))
            metrics.cvar_95 = float(RiskCalculator.calculate_cvar(returns, 0.95))
            metrics.cvar_99 = float(RiskCalculator.calculate_cvar(returns, 0.99))

            metrics.sharpe_ratio = float(RiskCalculator.calculate_sharpe_ratio(returns))
            metrics.sortino_ratio = float(RiskCalculator.calculate_sortino_ratio(returns))

            metrics.volatility_daily = float(returns.std())
            metrics.volatility_annualized = float(returns.std() * np.sqrt(252))

            if len(equity_curve) > 1:
                max_dd, dd_duration = RiskCalculator.calculate_max_drawdown(equity_curve)
                metrics.max_drawdown = float(max_dd)
                metrics.max_drawdown_duration = int(dd_duration)
                metrics.calmar_ratio = float(RiskCalculator.calculate_calmar_ratio(returns, equity_curve))

                # Current drawdown
                current_peak = equity_curve.expanding().max().iloc[-1]
                current_value = equity_curve.iloc[-1]
                metrics.current_drawdown = float(abs((current_value - current_peak) / current_peak))

            metrics.skewness = float(returns.skew())
            metrics.kurtosis = float(returns.kurtosis())

        return {
            "risk_metrics": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "calmar_ratio": metrics.calmar_ratio,
                "var_95": metrics.var_95,
                "var_99": metrics.var_99,
                "cvar_95": metrics.cvar_95,
                "cvar_99": metrics.cvar_99,
                "max_drawdown": metrics.max_drawdown,
                "max_drawdown_duration_days": metrics.max_drawdown_duration,
                "current_drawdown": metrics.current_drawdown,
                "volatility_daily": metrics.volatility_daily,
                "volatility_annualized": metrics.volatility_annualized,
                "skewness": metrics.skewness,
                "kurtosis": metrics.kurtosis
            },
            "calculation_period_days": len(summaries),
            "data_points": len(returns),
            "calculation_date": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        # Return mock data on error
        return _generate_mock_risk_metrics()


@router.get("/analytics/performance-metrics")
async def get_performance_metrics(
    days: int = 30,
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get performance metrics for the portfolio

    Returns:
    - Total return
    - CAGR
    - Win rate
    - Profit factor
    - Average win/loss
    - Best/worst day
    """
    try:
        # Get historical data
        stmt = select(PortfolioSummary).order_by(
            desc(PortfolioSummary.timestamp)
        ).limit(days)
        result = await db.execute(stmt)
        summaries = result.scalars().all()

        if not summaries:
            return _generate_mock_performance_metrics()

        df = pd.DataFrame([{
            'timestamp': s.timestamp,
            'total_value': s.total_value,
            'total_pnl': s.total_pnl
        } for s in summaries])

        df = df.sort_values('timestamp')
        df['returns'] = df['total_value'].pct_change()
        returns = df['returns'].dropna()

        # Calculate performance metrics
        total_return = (df['total_value'].iloc[-1] / df['total_value'].iloc[0] - 1) if len(df) > 1 else 0

        # CAGR
        periods = len(df)
        years = periods / 252  # Assuming daily data
        cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0

        # Win rate
        winning_days = (returns > 0).sum()
        total_days = len(returns)
        win_rate = winning_days / total_days if total_days > 0 else 0

        # Average win/loss
        winning_returns = returns[returns > 0]
        losing_returns = returns[returns < 0]

        avg_win = winning_returns.mean() if len(winning_returns) > 0 else 0
        avg_loss = abs(losing_returns.mean()) if len(losing_returns) > 0 else 0

        # Profit factor
        total_wins = winning_returns.sum() if len(winning_returns) > 0 else 0
        total_losses = abs(losing_returns.sum()) if len(losing_returns) > 0 else 0.0001
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Best/worst day
        best_day = returns.max() if len(returns) > 0 else 0
        worst_day = returns.min() if len(returns) > 0 else 0

        return {
            "performance_metrics": {
                "total_return": float(total_return),
                "total_return_pct": float(total_return * 100),
                "cagr": float(cagr),
                "cagr_pct": float(cagr * 100),
                "win_rate": float(win_rate),
                "win_rate_pct": float(win_rate * 100),
                "profit_factor": float(profit_factor),
                "average_win": float(avg_win),
                "average_win_pct": float(avg_win * 100),
                "average_loss": float(avg_loss),
                "average_loss_pct": float(avg_loss * 100),
                "best_day": float(best_day),
                "best_day_pct": float(best_day * 100),
                "worst_day": float(worst_day),
                "worst_day_pct": float(worst_day * 100),
                "total_trading_days": int(total_days),
                "winning_days": int(winning_days),
                "losing_days": int(total_days - winning_days)
            },
            "calculation_period_days": len(summaries),
            "calculation_date": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        return _generate_mock_performance_metrics()


@router.get("/analytics/drawdown-analysis")
async def get_drawdown_analysis(
    days: int = 90,
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Detailed drawdown analysis

    Returns:
    - Drawdown series
    - Maximum drawdown
    - Current drawdown
    - Recovery periods
    """
    try:
        stmt = select(PortfolioSummary).order_by(
            desc(PortfolioSummary.timestamp)
        ).limit(days)
        result = await db.execute(stmt)
        summaries = result.scalars().all()

        if not summaries:
            return {"error": "No historical data available"}

        df = pd.DataFrame([{
            'timestamp': s.timestamp,
            'total_value': s.total_value
        } for s in summaries])

        df = df.sort_values('timestamp')
        equity_curve = df['total_value']

        # Calculate running maximum
        running_max = equity_curve.expanding().max()

        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max
        drawdown_pct = drawdown * 100

        # Maximum drawdown
        max_dd, dd_duration = RiskCalculator.calculate_max_drawdown(equity_curve)

        # Current drawdown
        current_peak = running_max.iloc[-1]
        current_value = equity_curve.iloc[-1]
        current_dd = abs((current_value - current_peak) / current_peak)

        # Drawdown periods
        in_drawdown = False
        drawdown_periods = []
        start_idx = 0

        for idx, dd_val in enumerate(drawdown):
            if dd_val < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = idx
            elif dd_val >= 0 and in_drawdown:
                in_drawdown = False
                drawdown_periods.append({
                    "start_date": df.iloc[start_idx]['timestamp'].isoformat(),
                    "end_date": df.iloc[idx]['timestamp'].isoformat(),
                    "duration_days": idx - start_idx,
                    "max_drawdown": float(drawdown[start_idx:idx].min())
                })

        # Top 5 worst drawdowns
        top_drawdowns = sorted(drawdown_periods, key=lambda x: x['max_drawdown'])[:5]

        return {
            "drawdown_analysis": {
                "max_drawdown": float(max_dd),
                "max_drawdown_pct": float(max_dd * 100),
                "max_drawdown_duration_days": int(dd_duration),
                "current_drawdown": float(current_dd),
                "current_drawdown_pct": float(current_dd * 100),
                "in_drawdown": current_dd > 0.01,  # More than 1% drawdown
                "total_drawdown_periods": len(drawdown_periods),
                "average_drawdown_duration": float(np.mean([p['duration_days'] for p in drawdown_periods])) if drawdown_periods else 0
            },
            "top_5_worst_drawdowns": top_drawdowns,
            "calculation_period_days": len(summaries),
            "calculation_date": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error analyzing drawdowns: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing drawdowns: {str(e)}")


@router.get("/analytics/position-size-recommendation")
async def get_position_size_recommendation(
    symbol: str,
    method: str = "fixed_fractional",
    win_rate: float = 0.55,
    avg_win: float = 0.02,
    avg_loss: float = 0.015,
    risk_per_trade: float = 0.02,
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get recommended position size for a symbol

    Methods:
    - kelly: Kelly Criterion
    - fixed_fractional: Fixed percentage risk
    - volatility_adjusted: Volatility-based sizing
    """
    try:
        # Get latest portfolio value
        stmt = select(PortfolioSummary).order_by(desc(PortfolioSummary.timestamp))
        result = await db.execute(stmt)
        summary = result.scalar_one_or_none()

        if not summary:
            raise HTTPException(status_code=404, detail="No portfolio data available")

        account_balance = summary.total_value

        # Calculate position size using risk manager
        from src.core.risk_manager import PositionSizer

        if method == "kelly":
            kelly_fraction = PositionSizer.kelly_criterion(
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                max_fraction=0.25
            )
            recommended_size = account_balance * kelly_fraction

            return {
                "symbol": symbol,
                "method": "Kelly Criterion",
                "recommended_position_size": float(recommended_size),
                "allocation_percentage": float(kelly_fraction * 100),
                "parameters": {
                    "win_rate": win_rate,
                    "avg_win": avg_win,
                    "avg_loss": avg_loss
                },
                "account_balance": float(account_balance)
            }

        elif method == "fixed_fractional":
            recommended_size = PositionSizer.fixed_fractional(
                account_balance=account_balance,
                risk_per_trade=risk_per_trade
            )

            return {
                "symbol": symbol,
                "method": "Fixed Fractional",
                "recommended_position_size": float(recommended_size),
                "allocation_percentage": float(risk_per_trade * 100),
                "parameters": {
                    "risk_per_trade": risk_per_trade
                },
                "account_balance": float(account_balance)
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating position size: {str(e)}")


# ===================================
# HELPER FUNCTIONS
# ===================================

def _generate_mock_risk_metrics() -> Dict[str, Any]:
    """Generate mock risk metrics for testing"""
    return {
        "risk_metrics": {
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "calmar_ratio": 0.8,
            "var_95": 0.02,
            "var_99": 0.035,
            "cvar_95": 0.025,
            "cvar_99": 0.04,
            "max_drawdown": 0.08,
            "max_drawdown_duration_days": 15,
            "current_drawdown": 0.02,
            "volatility_daily": 0.015,
            "volatility_annualized": 0.238,
            "skewness": -0.3,
            "kurtosis": 3.5
        },
        "calculation_period_days": 30,
        "data_points": 30,
        "calculation_date": datetime.now().isoformat(),
        "note": "Mock data - no historical portfolio data available"
    }


def _generate_mock_performance_metrics() -> Dict[str, Any]:
    """Generate mock performance metrics for testing"""
    return {
        "performance_metrics": {
            "total_return": 0.15,
            "total_return_pct": 15.0,
            "cagr": 0.18,
            "cagr_pct": 18.0,
            "win_rate": 0.58,
            "win_rate_pct": 58.0,
            "profit_factor": 1.8,
            "average_win": 0.025,
            "average_win_pct": 2.5,
            "average_loss": 0.018,
            "average_loss_pct": 1.8,
            "best_day": 0.05,
            "best_day_pct": 5.0,
            "worst_day": -0.04,
            "worst_day_pct": -4.0,
            "total_trading_days": 30,
            "winning_days": 17,
            "losing_days": 13
        },
        "calculation_period_days": 30,
        "calculation_date": datetime.now().isoformat(),
        "note": "Mock data - no historical portfolio data available"
    }
