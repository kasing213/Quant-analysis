from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import List, Optional, Dict, Any


def fixtures_enabled() -> bool:
    """Return True when we should serve dashboard fixtures."""
    enable_fixtures = os.getenv("ENABLE_DASHBOARD_FIXTURES", "true").lower() == "true"
    test_mode = os.getenv("BINANCE_TEST_MODE", "false").lower() == "true"
    return enable_fixtures and test_mode


def _now(offset_days: int = 0, offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=offset_days, minutes=offset_minutes)


def get_mock_portfolio_summary() -> Dict[str, Any]:
    """Single snapshot totalling roughly $10,000."""
    return {
        "id": 0,
        "timestamp": _now(),
        "total_value": Decimal("10000.00"),
        "cash": Decimal("4199.70"),
        "positions_value": Decimal("5800.30"),
        "total_pnl": Decimal("678.45"),
        "day_pnl": Decimal("82.65"),
    }


def get_mock_portfolio_history(samples: int = 7) -> List[Dict[str, Any]]:
    """Generate a short history of portfolio values."""
    history: List[Dict[str, Any]] = []
    base_value = Decimal("9420.00")
    cash_value = Decimal("4199.70")
    for index in range(samples):
        day_offset = samples - index
        value = base_value + Decimal(str(index * 92.5))
        history.append({
            "id": index,
            "timestamp": _now(offset_days=day_offset),
            "total_value": value,
            "cash": cash_value,
            "positions_value": value - cash_value,
            "total_pnl": value - Decimal("9320.00"),
            "day_pnl": Decimal("58.10"),
        })
    history.append(get_mock_portfolio_summary())
    return history


def get_mock_positions() -> List[Dict[str, Any]]:
    now = _now()
    return [
        {
            "id": 1,
            "symbol": "BTCUSDT",
            "quantity": Decimal("0.060"),
            "avg_cost": Decimal("50500.00"),
            "current_price": Decimal("52000.00"),
            "market_value": Decimal("3120.00"),
            "unrealized_pnl": Decimal("90.00"),
            "created_at": now - timedelta(days=10),
            "updated_at": now,
        },
        {
            "id": 2,
            "symbol": "ETHUSDT",
            "quantity": Decimal("0.700"),
            "avg_cost": Decimal("3600.00"),
            "current_price": Decimal("3829.00"),
            "market_value": Decimal("2680.30"),
            "unrealized_pnl": Decimal("160.30"),
            "created_at": now - timedelta(days=7),
            "updated_at": now,
        },
    ]


def get_mock_trades() -> List[Dict[str, Any]]:
    now = _now()
    return [
        {
            "id": 1,
            "timestamp": now - timedelta(hours=6),
            "symbol": "BTCUSDT",
            "action": "BUY",
            "quantity": Decimal("0.040"),
            "price": Decimal("49500.00"),
            "value": Decimal("1980.00"),
            "commission": Decimal("0.80"),
        },
        {
            "id": 2,
            "timestamp": now - timedelta(hours=3),
            "symbol": "ETHUSDT",
            "action": "BUY",
            "quantity": Decimal("0.500"),
            "price": Decimal("3605.00"),
            "value": Decimal("1802.50"),
            "commission": Decimal("0.70"),
        },
        {
            "id": 3,
            "timestamp": now - timedelta(hours=1),
            "symbol": "BTCUSDT",
            "action": "SELL",
            "quantity": Decimal("0.020"),
            "price": Decimal("52550.00"),
            "value": Decimal("1051.00"),
            "commission": Decimal("0.45"),
        },
    ]


def filter_mock_trades(
    trades: List[Dict[str, Any]],
    symbol: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    filtered = trades

    if symbol:
        filtered = [trade for trade in filtered if trade["symbol"].upper() == symbol.upper()]

    if action:
        filtered = [trade for trade in filtered if trade["action"].upper() == action.upper()]

    if start_date:
        filtered = [trade for trade in filtered if trade["timestamp"].date() >= start_date]

    if end_date:
        filtered = [trade for trade in filtered if trade["timestamp"].date() < end_date]

    return filtered
