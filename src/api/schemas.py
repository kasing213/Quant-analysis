from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

class PositionBase(BaseModel):
    symbol: str = Field(..., max_length=20)
    quantity: Decimal = Field(..., decimal_places=6)
    avg_cost: Decimal = Field(..., decimal_places=6)
    current_price: Optional[Decimal] = Field(None, decimal_places=6)
    market_value: Optional[Decimal] = Field(None, decimal_places=6)
    unrealized_pnl: Optional[Decimal] = Field(None, decimal_places=6)

class PositionCreate(PositionBase):
    pass

class Position(PositionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TradeBase(BaseModel):
    symbol: str = Field(..., max_length=20)
    action: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: Decimal = Field(..., decimal_places=6)
    price: Decimal = Field(..., decimal_places=6)
    value: Decimal = Field(..., decimal_places=6)
    commission: Optional[Decimal] = Field(0, decimal_places=6)

class TradeCreate(TradeBase):
    pass

class Trade(TradeBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class PortfolioSummaryBase(BaseModel):
    total_value: Decimal = Field(..., decimal_places=6)
    cash: Decimal = Field(..., decimal_places=6)
    positions_value: Decimal = Field(..., decimal_places=6)
    total_pnl: Decimal = Field(..., decimal_places=6)
    day_pnl: Decimal = Field(..., decimal_places=6)

class PortfolioSummaryCreate(PortfolioSummaryBase):
    pass

class PortfolioSummary(PortfolioSummaryBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class PipelineDescriptor(BaseModel):
    id: str
    label: str


class PipelineStatus(BaseModel):
    current: PipelineDescriptor
    options: List[PipelineDescriptor]


class PipelineSelectRequest(BaseModel):
    pipeline_id: str


class PipelineValidationResult(BaseModel):
    """Result of pipeline configuration validation"""
    pipeline: str
    valid: bool
    errors: List[str]
    summary: Dict[str, Any]


class PipelineConfigSummary(BaseModel):
    """Detailed pipeline configuration information"""
    pipeline: str
    services: Dict[str, Any]
    credentials_configured: bool
    redis_database: int
    testnet_mode: Optional[bool] = None
    test_mode: Optional[bool] = None
