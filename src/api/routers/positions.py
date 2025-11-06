import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from ..database import get_async_db
from ..models import Position
from ..schemas import Position as PositionSchema, PositionCreate
from ..mock_data import fixtures_enabled, get_mock_positions

router = APIRouter(prefix="/positions", tags=["positions"])
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[PositionSchema])
async def get_all_positions(db: AsyncSession = Depends(get_async_db)):
    """Get all current positions"""
    positions = []
    try:
        stmt = select(Position).where(Position.quantity != 0)
        result = await db.execute(stmt)
        positions = result.scalars().all()
    except Exception as exc:
        logger.warning("Positions query failed, using fixtures: %s", exc)

    if positions:
        return positions

    if fixtures_enabled():
        return [PositionSchema(**pos) for pos in get_mock_positions()]

    return []

@router.get("/{symbol}", response_model=PositionSchema)
async def get_position(symbol: str, db: AsyncSession = Depends(get_async_db)):
    """Get position for a specific symbol"""
    try:
        stmt = select(Position).where(Position.symbol == symbol.upper())
        result = await db.execute(stmt)
        position = result.scalar_one_or_none()
        if position:
            return position
    except Exception as exc:
        logger.warning("Position lookup failed for %s, using fixtures: %s", symbol, exc)

    if fixtures_enabled():
        for pos in get_mock_positions():
            if pos["symbol"] == symbol.upper():
                return PositionSchema(**pos)

    raise HTTPException(status_code=404, detail=f"Position for {symbol} not found")

@router.post("/", response_model=PositionSchema)
async def create_or_update_position(position: PositionCreate, db: AsyncSession = Depends(get_async_db)):
    """Create or update a position"""
    symbol = position.symbol.upper()

    # Check if position already exists
    stmt = select(Position).where(Position.symbol == symbol)
    result = await db.execute(stmt)
    existing_position = result.scalar_one_or_none()

    if existing_position:
        # Update existing position
        for field, value in position.model_dump().items():
            setattr(existing_position, field, value)
        await db.flush()
        await db.refresh(existing_position)
        return existing_position
    else:
        # Create new position
        db_position = Position(**position.model_dump())
        db_position.symbol = symbol
        db.add(db_position)
        await db.flush()
        await db.refresh(db_position)
        return db_position

@router.delete("/{symbol}")
async def delete_position(symbol: str, db: AsyncSession = Depends(get_async_db)):
    """Delete a position"""
    position = db.query(Position).filter(Position.symbol == symbol.upper()).first()
    if not position:
        raise HTTPException(status_code=404, detail=f"Position for {symbol} not found")

    db.delete(position)
    db.commit()
    return {"message": f"Position for {symbol} deleted successfully"}
