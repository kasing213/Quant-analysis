"""
Backtesting API Router
Provides endpoints for running backtests and retrieving results
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
import json
import pandas as pd
from pathlib import Path

from ..database import get_async_db
from ...core.enhanced_backtester import QuantBacktester, MovingAverageStrategy, MeanReversionStrategy
from ...core.advanced_risk_manager import create_enhanced_risk_manager
from ...core.pg_portfolio_manager import PostgreSQLPortfolioManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtesting", tags=["backtesting"])

# In-memory storage for backtest results (in production, use Redis or database)
backtest_results_cache = {}

@router.post("/run")
async def run_backtest(
    strategy: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    strategy_params: Optional[Dict] = None,
    background_tasks: BackgroundTasks = None,
    db = Depends(get_async_db)
):
    """Run a backtest with specified parameters"""

    try:
        # Validate inputs
        if not symbols:
            raise HTTPException(status_code=400, detail="At least one symbol is required")

        # Parse dates
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate backtest ID
        backtest_id = f"bt_{int(datetime.now().timestamp())}"

        # Default strategy parameters
        if strategy_params is None:
            strategy_params = {}

        # Initialize backtest result entry
        backtest_results_cache[backtest_id] = {
            "status": "running",
            "progress": 0,
            "started_at": datetime.now().isoformat(),
            "parameters": {
                "strategy": strategy,
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "strategy_params": strategy_params
            }
        }

        # Run backtest in background
        if background_tasks:
            background_tasks.add_task(
                _run_backtest_task,
                backtest_id, strategy, symbols, start_dt, end_dt,
                initial_capital, strategy_params
            )
        else:
            # Run synchronously for immediate results (smaller datasets)
            await _run_backtest_task(
                backtest_id, strategy, symbols, start_dt, end_dt,
                initial_capital, strategy_params
            )

        return {
            "backtest_id": backtest_id,
            "status": "initiated",
            "message": "Backtest started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _run_backtest_task(backtest_id: str, strategy: str, symbols: List[str],
                           start_date: datetime, end_date: datetime,
                           initial_capital: float, strategy_params: Dict):
    """Background task to run the actual backtest"""

    try:
        # Update progress
        backtest_results_cache[backtest_id]["progress"] = 10

        # Initialize backtester
        backtester = QuantBacktester(initial_capital=initial_capital)

        # Update progress
        backtest_results_cache[backtest_id]["progress"] = 20

        # Add data for each symbol
        for i, symbol in enumerate(symbols):
            try:
                backtester.add_data(symbol, start_date, end_date)
                progress = 20 + (i + 1) * (40 / len(symbols))
                backtest_results_cache[backtest_id]["progress"] = int(progress)
            except Exception as e:
                logger.warning(f"Failed to add data for {symbol}: {e}")

        # Add strategy
        if strategy == "moving_average":
            strategy_class = MovingAverageStrategy
        elif strategy == "mean_reversion":
            strategy_class = MeanReversionStrategy
        else:
            strategy_class = MovingAverageStrategy  # Default

        backtester.add_strategy(strategy_class, **strategy_params)

        # Update progress
        backtest_results_cache[backtest_id]["progress"] = 70

        # Run backtest
        results = backtester.run()

        # Update progress
        backtest_results_cache[backtest_id]["progress"] = 90

        # Generate comprehensive results
        performance_stats = backtester.get_performance_stats()
        trades_analysis = backtester.get_trades_analysis()
        risk_metrics = backtester.get_risk_metrics()

        # Create portfolio manager for risk analysis
        portfolio_manager = PostgreSQLPortfolioManager()
        risk_manager = create_enhanced_risk_manager(portfolio_manager)

        # Update progress
        backtest_results_cache[backtest_id]["progress"] = 95

        # Store final results
        final_results = {
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.now().isoformat(),
            "results": {
                "performance": performance_stats,
                "trades": trades_analysis,
                "risk_metrics": risk_metrics,
                "equity_curve": backtester.get_equity_curve(),
                "drawdown_analysis": backtester.get_drawdown_analysis(),
                "monthly_returns": backtester.get_monthly_returns(),
                "yearly_returns": backtester.get_yearly_returns()
            },
            "charts": {
                "equity_curve_url": f"/api/v1/backtesting/{backtest_id}/charts/equity",
                "drawdown_url": f"/api/v1/backtesting/{backtest_id}/charts/drawdown",
                "monthly_returns_url": f"/api/v1/backtesting/{backtest_id}/charts/monthly_returns"
            }
        }

        # Merge with existing data
        backtest_results_cache[backtest_id].update(final_results)

        logger.info(f"Backtest {backtest_id} completed successfully")

    except Exception as e:
        logger.error(f"Error running backtest {backtest_id}: {e}")
        backtest_results_cache[backtest_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

@router.get("/results/{backtest_id}")
async def get_backtest_results(backtest_id: str):
    """Get backtest results by ID"""

    if backtest_id not in backtest_results_cache:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return backtest_results_cache[backtest_id]

@router.get("/list")
async def list_backtests():
    """List all backtests"""

    backtests = []
    for bt_id, bt_data in backtest_results_cache.items():
        backtests.append({
            "backtest_id": bt_id,
            "status": bt_data.get("status"),
            "progress": bt_data.get("progress", 0),
            "started_at": bt_data.get("started_at"),
            "completed_at": bt_data.get("completed_at"),
            "parameters": bt_data.get("parameters", {})
        })

    # Sort by start time (newest first)
    backtests.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return {"backtests": backtests}

@router.delete("/results/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """Delete a backtest result"""

    if backtest_id not in backtest_results_cache:
        raise HTTPException(status_code=404, detail="Backtest not found")

    del backtest_results_cache[backtest_id]

    return {"message": "Backtest deleted successfully"}

@router.get("/strategies")
async def get_available_strategies():
    """Get list of available trading strategies"""

    strategies = [
        {
            "name": "moving_average",
            "display_name": "Moving Average Crossover",
            "description": "Simple moving average crossover strategy with stop-loss and take-profit",
            "parameters": {
                "fast_period": {"type": "int", "default": 10, "min": 5, "max": 50},
                "slow_period": {"type": "int", "default": 30, "min": 20, "max": 200},
                "stop_loss": {"type": "float", "default": 0.05, "min": 0.01, "max": 0.20},
                "take_profit": {"type": "float", "default": 0.15, "min": 0.05, "max": 0.50}
            }
        },
        {
            "name": "mean_reversion",
            "display_name": "Mean Reversion",
            "description": "Mean reversion strategy using RSI and Bollinger Bands",
            "parameters": {
                "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
                "rsi_oversold": {"type": "float", "default": 30, "min": 10, "max": 40},
                "rsi_overbought": {"type": "float", "default": 70, "min": 60, "max": 90},
                "bb_period": {"type": "int", "default": 20, "min": 10, "max": 50},
                "bb_std": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0}
            }
        }
    ]

    return {"strategies": strategies}

@router.get("/performance/compare")
async def compare_backtests(backtest_ids: str):
    """Compare multiple backtest results"""

    bt_ids = backtest_ids.split(",")

    if len(bt_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 backtest IDs required for comparison")

    comparison_data = {}

    for bt_id in bt_ids:
        if bt_id not in backtest_results_cache:
            raise HTTPException(status_code=404, detail=f"Backtest {bt_id} not found")

        bt_data = backtest_results_cache[bt_id]
        if bt_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail=f"Backtest {bt_id} is not completed")

        results = bt_data.get("results", {})
        performance = results.get("performance", {})

        comparison_data[bt_id] = {
            "strategy": bt_data.get("parameters", {}).get("strategy"),
            "total_return": performance.get("total_return"),
            "annual_return": performance.get("annual_return"),
            "sharpe_ratio": performance.get("sharpe_ratio"),
            "max_drawdown": performance.get("max_drawdown"),
            "volatility": performance.get("volatility"),
            "win_rate": performance.get("win_rate"),
            "profit_factor": performance.get("profit_factor"),
            "total_trades": performance.get("total_trades")
        }

    # Calculate rankings
    metrics = ["total_return", "annual_return", "sharpe_ratio", "win_rate", "profit_factor"]
    rankings = {}

    for metric in metrics:
        values = [(bt_id, data.get(metric, 0)) for bt_id, data in comparison_data.items()]
        # Sort descending (higher is better)
        if metric == "max_drawdown":
            values.sort(key=lambda x: abs(x[1]))  # Lower drawdown is better
        else:
            values.sort(key=lambda x: x[1], reverse=True)

        rankings[metric] = {bt_id: rank + 1 for rank, (bt_id, _) in enumerate(values)}

    return {
        "comparison": comparison_data,
        "rankings": rankings,
        "summary": {
            "best_total_return": max(comparison_data.items(), key=lambda x: x[1].get("total_return", 0)),
            "best_sharpe": max(comparison_data.items(), key=lambda x: x[1].get("sharpe_ratio", 0)),
            "lowest_drawdown": min(comparison_data.items(), key=lambda x: abs(x[1].get("max_drawdown", 0)))
        }
    }

@router.get("/{backtest_id}/charts/{chart_type}")
async def get_backtest_chart(backtest_id: str, chart_type: str):
    """Get chart data for a specific backtest"""

    if backtest_id not in backtest_results_cache:
        raise HTTPException(status_code=404, detail="Backtest not found")

    bt_data = backtest_results_cache[backtest_id]

    if bt_data.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Backtest not completed")

    results = bt_data.get("results", {})

    if chart_type == "equity":
        return results.get("equity_curve", [])
    elif chart_type == "drawdown":
        return results.get("drawdown_analysis", [])
    elif chart_type == "monthly_returns":
        return results.get("monthly_returns", [])
    elif chart_type == "yearly_returns":
        return results.get("yearly_returns", [])
    else:
        raise HTTPException(status_code=400, detail="Invalid chart type")

@router.post("/optimize")
async def optimize_strategy(
    strategy: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    parameter_ranges: Dict[str, Dict],
    optimization_metric: str = "sharpe_ratio",
    max_iterations: int = 50,
    background_tasks: BackgroundTasks = None
):
    """Run strategy parameter optimization"""

    # This would implement parameter optimization using techniques like:
    # - Grid search
    # - Random search
    # - Bayesian optimization
    # - Genetic algorithms

    optimization_id = f"opt_{int(datetime.now().timestamp())}"

    # For now, return a placeholder response
    return {
        "optimization_id": optimization_id,
        "status": "initiated",
        "message": "Strategy optimization started",
        "estimated_completion": (datetime.now() + timedelta(minutes=10)).isoformat()
    }

@router.get("/market-data/symbols")
async def get_available_symbols():
    """Get list of available symbols for backtesting"""

    # Common symbols for backtesting
    symbols = [
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Technology"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "sector": "Technology"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Technology"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "sector": "ETF"},
        {"symbol": "QQQ", "name": "Invesco QQQ ETF", "sector": "ETF"},
        {"symbol": "GLD", "name": "SPDR Gold Trust", "sector": "Commodities"},
        {"symbol": "TLT", "name": "iShares 20+ Year Treasury ETF", "sector": "Fixed Income"}
    ]

    return {"symbols": symbols}

@router.get("/reports/summary")
async def get_backtesting_summary():
    """Get summary of all backtesting activity"""

    total_backtests = len(backtest_results_cache)
    completed_backtests = sum(1 for bt in backtest_results_cache.values() if bt.get("status") == "completed")
    failed_backtests = sum(1 for bt in backtest_results_cache.values() if bt.get("status") == "failed")
    running_backtests = sum(1 for bt in backtest_results_cache.values() if bt.get("status") == "running")

    # Get performance statistics from completed backtests
    performance_stats = []
    for bt_data in backtest_results_cache.values():
        if bt_data.get("status") == "completed" and "results" in bt_data:
            perf = bt_data["results"].get("performance", {})
            performance_stats.append({
                "total_return": perf.get("total_return", 0),
                "sharpe_ratio": perf.get("sharpe_ratio", 0),
                "max_drawdown": perf.get("max_drawdown", 0)
            })

    avg_performance = {}
    if performance_stats:
        avg_performance = {
            "avg_total_return": sum(p["total_return"] for p in performance_stats) / len(performance_stats),
            "avg_sharpe_ratio": sum(p["sharpe_ratio"] for p in performance_stats) / len(performance_stats),
            "avg_max_drawdown": sum(p["max_drawdown"] for p in performance_stats) / len(performance_stats)
        }

    return {
        "summary": {
            "total_backtests": total_backtests,
            "completed": completed_backtests,
            "failed": failed_backtests,
            "running": running_backtests,
            "success_rate": (completed_backtests / total_backtests * 100) if total_backtests > 0 else 0
        },
        "performance": avg_performance,
        "recent_activity": list(backtest_results_cache.values())[-5:]  # Last 5 backtests
    }