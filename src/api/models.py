from sqlalchemy import Column, String, DateTime, Text, Numeric, ForeignKey, Enum, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from .database import Base

# Enum classes for type safety
class AccountType(str, enum.Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    DEMO = "DEMO"

class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"

class InstrumentType(str, enum.Enum):
    STOCK = "STOCK"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    CFD = "CFD"

class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"

class TradeAction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"
    BUY_TO_COVER = "BUY_TO_COVER"

class TradeType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class RiskSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "trading"}

    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_name = Column(String(100), nullable=False)
    account_type = Column(Enum(AccountType), nullable=False)
    initial_capital = Column(Numeric(20, 8), nullable=False, default=0)
    current_balance = Column(Numeric(20, 8), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE)

    # Relationships
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="account", cascade="all, delete-orphan")
    portfolio_summaries = relationship("PortfolioSummary", back_populates="account", cascade="all, delete-orphan")
    risk_events = relationship("RiskEvent", back_populates="account", cascade="all, delete-orphan")

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = {"schema": "trading"}

    position_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("trading.accounts.account_id"), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    instrument_type = Column(Enum(InstrumentType), default=InstrumentType.STOCK)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_cost = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8))
    market_value = Column(Numeric(20, 8))
    unrealized_pnl = Column(Numeric(20, 8))
    realized_pnl = Column(Numeric(20, 8), default=0)
    position_side = Column(Enum(PositionSide), nullable=False)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Enum(PositionStatus), default=PositionStatus.OPEN)

    # Relationships
    account = relationship("Account", back_populates="positions")
    trades = relationship("Trade", back_populates="position")

class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "trading"}

    trade_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("trading.accounts.account_id"), nullable=False)
    position_id = Column(UUID(as_uuid=True), ForeignKey("trading.positions.position_id"), nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    instrument_type = Column(Enum(InstrumentType), default=InstrumentType.STOCK)
    order_id = Column(String(100))
    execution_id = Column(String(100))
    action = Column(Enum(TradeAction), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    value = Column(Numeric(20, 8), nullable=False)
    commission = Column(Numeric(20, 8), default=0)
    fees = Column(Numeric(20, 8), default=0)
    tax = Column(Numeric(20, 8), default=0)
    realized_pnl = Column(Numeric(20, 8), default=0)
    exchange = Column(String(50))
    currency = Column(String(10), default="USD")
    execution_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trade_type = Column(Enum(TradeType), default=TradeType.MARKET)
    strategy_name = Column(String(100))
    notes = Column(Text)

    # Relationships
    account = relationship("Account", back_populates="trades")
    position = relationship("Position", back_populates="trades")

class PortfolioSummary(Base):
    __tablename__ = "portfolio_summary"
    __table_args__ = {"schema": "trading"}

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("trading.accounts.account_id"), nullable=False)
    total_value = Column(Numeric(20, 8), nullable=False)
    cash = Column(Numeric(20, 8), nullable=False)
    positions_value = Column(Numeric(20, 8), nullable=False)
    total_pnl = Column(Numeric(20, 8), nullable=False)
    day_pnl = Column(Numeric(20, 8), nullable=False)
    unrealized_pnl = Column(Numeric(20, 8), nullable=False)
    realized_pnl = Column(Numeric(20, 8), nullable=False)
    buying_power = Column(Numeric(20, 8))
    margin_used = Column(Numeric(20, 8), default=0)
    risk_metrics = Column(JSONB)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    account = relationship("Account", back_populates="portfolio_summaries")

class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = {"schema": "trading"}

    symbol = Column(String(20), primary_key=True)
    timestamp = Column(DateTime(timezone=True), primary_key=True)
    open_price = Column(Numeric(20, 8))
    high_price = Column(Numeric(20, 8))
    low_price = Column(Numeric(20, 8))
    close_price = Column(Numeric(20, 8))
    volume = Column(Numeric(20, 0))
    adj_close = Column(Numeric(20, 8))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = {"schema": "trading"}

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("trading.accounts.account_id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    severity = Column(Enum(RiskSeverity))
    description = Column(Text, nullable=False)
    risk_metrics = Column(JSONB)
    action_taken = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))

    # Relationships
    account = relationship("Account", back_populates="risk_events")