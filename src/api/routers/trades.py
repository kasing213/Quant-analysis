import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_async_db
from ..models import Trade
from ..schemas import Trade as TradeSchema, TradeCreate
from ..mock_data import fixtures_enabled, get_mock_trades, filter_mock_trades

router = APIRouter(prefix="/trades", tags=["trades"])
logger = logging.getLogger(__name__)


def _serialize_trade(trade: Trade) -> TradeSchema:
    """Convert SQLAlchemy Trade model to API schema."""
    try:
        return TradeSchema(
            id=abs(hash(trade.trade_id)) % 1_000_000_000,
            timestamp=trade.execution_time or trade.created_at,
            symbol=trade.symbol,
            action=trade.action.value if hasattr(trade.action, "value") else trade.action,
            quantity=trade.quantity,
            price=trade.price,
            value=trade.value,
            commission=trade.commission,
        )
    except Exception as exc:
        logger.warning("Failed to serialize trade %s: %s", getattr(trade, "trade_id", ""), exc)
        raise


def _fixture_trades(
    symbol: Optional[str],
    action: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
    offset: int,
) -> List[TradeSchema]:
    mock_trades = filter_mock_trades(
        get_mock_trades(),
        symbol=symbol,
        action=action,
        start_date=start_date,
        end_date=end_date,
    )
    paginated = mock_trades[offset: offset + limit]
    return [TradeSchema(**trade) for trade in paginated]


@router.get("/", response_model=List[TradeSchema])
async def get_trades(
    symbol: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """Get trades with optional filtering."""

    if fixtures_enabled():
        return _fixture_trades(symbol, action, start_date, end_date, limit, offset)

    trades: List[TradeSchema] = []
    try:
        stmt = select(Trade).order_by(desc(Trade.execution_time)).offset(offset).limit(limit)

        if symbol:
            stmt = stmt.where(Trade.symbol == symbol.upper())

        if action:
            stmt = stmt.where(Trade.action == action.upper())

        if start_date:
            stmt = stmt.where(Trade.execution_time >= datetime.combine(start_date, datetime.min.time()))

        if end_date:
            stmt = stmt.where(Trade.execution_time < datetime.combine(end_date, datetime.min.time()))

        result = await db.execute(stmt)
        records = result.scalars().all()
        trades = [_serialize_trade(trade) for trade in records]
    except Exception as exc:
        logger.warning("Trade query failed, falling back to fixtures: %s", exc)

    if trades:
        return trades

    if fixtures_enabled():
        return _fixture_trades(symbol, action, start_date, end_date, limit, offset)

    return []


@router.get("/{trade_id}", response_model=TradeSchema)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a specific trade by ID."""
    if fixtures_enabled():
        for item in get_mock_trades():
            if item["id"] == trade_id:
                return TradeSchema(**item)

    try:
        stmt = select(Trade).where(Trade.trade_id == trade_id)
        result = await db.execute(stmt)
        trade = result.scalar_one_or_none()
        if trade:
            return _serialize_trade(trade)
    except Exception as exc:
        logger.warning("Trade lookup failed for %s, falling back to fixtures: %s", trade_id, exc)

    raise HTTPException(status_code=404, detail="Trade not found")


@router.post("/", response_model=TradeSchema)
async def create_trade(trade: TradeCreate, db: AsyncSession = Depends(get_async_db)):
    """Create a new trade."""
    if fixtures_enabled():
        raise HTTPException(
            status_code=503,
            detail="Trade creation is disabled while fixtures are active.",
        )

    db_trade = Trade(**trade.model_dump())
    db_trade.symbol = trade.symbol.upper()
    db_trade.action = trade.action.upper()

    db.add(db_trade)
    await db.flush()
    await db.refresh(db_trade)
    await db.commit()
    return _serialize_trade(db_trade)


@router.get("/symbol/{symbol}", response_model=List[TradeSchema])
async def get_trades_by_symbol(
    symbol: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    """Get all trades for a specific symbol."""

    if fixtures_enabled():
        filtered = filter_mock_trades(get_mock_trades(), symbol=symbol)
        return [TradeSchema(**trade) for trade in filtered[:limit]]

    trades: List[TradeSchema] = []
    try:
        stmt = (
            select(Trade)
            .where(Trade.symbol == symbol.upper())
            .order_by(desc(Trade.execution_time))
            .limit(limit)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()
        trades = [_serialize_trade(trade) for trade in records]
    except Exception as exc:
        logger.warning("Trades by symbol query failed for %s, using fixtures: %s", symbol, exc)

    if trades:
        return trades

    return []
