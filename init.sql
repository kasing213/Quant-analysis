-- Quantitative Trading Database Schema
-- Initialize database with comprehensive schema for professional trading

-- Set timezone to UTC for consistent time handling
SET timezone = 'UTC';

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create trading schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Set search path
SET search_path TO trading, public;

-- =============================================
-- CORE TABLES
-- =============================================

-- Accounts table for multiple trading accounts
CREATE TABLE IF NOT EXISTS trading.accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('LIVE', 'PAPER', 'DEMO')),
    initial_capital DECIMAL(20, 8) NOT NULL DEFAULT 0,
    current_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED'))
);

-- Positions table with enhanced fields for quantitative analysis
CREATE TABLE IF NOT EXISTS trading.positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20) DEFAULT 'STOCK' CHECK (instrument_type IN ('STOCK', 'OPTION', 'FUTURE', 'FOREX', 'CRYPTO', 'CFD')),
    quantity DECIMAL(20, 8) NOT NULL,
    avg_cost DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    market_value DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    position_side VARCHAR(10) NOT NULL CHECK (position_side IN ('LONG', 'SHORT')),
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'PARTIALLY_CLOSED'))
);

-- Trades table with comprehensive execution details
CREATE TABLE IF NOT EXISTS trading.trades (
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    position_id UUID REFERENCES trading.positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20) DEFAULT 'STOCK',
    order_id VARCHAR(100),
    execution_id VARCHAR(100),
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL', 'SELL_SHORT', 'BUY_TO_COVER')),
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    value DECIMAL(20, 8) NOT NULL,
    commission DECIMAL(20, 8) DEFAULT 0,
    fees DECIMAL(20, 8) DEFAULT 0,
    tax DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    exchange VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'USD',
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    trade_type VARCHAR(20) DEFAULT 'MARKET' CHECK (trade_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    strategy_name VARCHAR(100),
    notes TEXT
);

-- Portfolio summary with enhanced metrics
CREATE TABLE IF NOT EXISTS trading.portfolio_summary (
    summary_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    total_value DECIMAL(20, 8) NOT NULL,
    cash DECIMAL(20, 8) NOT NULL,
    positions_value DECIMAL(20, 8) NOT NULL,
    total_pnl DECIMAL(20, 8) NOT NULL,
    day_pnl DECIMAL(20, 8) NOT NULL,
    unrealized_pnl DECIMAL(20, 8) NOT NULL,
    realized_pnl DECIMAL(20, 8) NOT NULL,
    buying_power DECIMAL(20, 8),
    margin_used DECIMAL(20, 8) DEFAULT 0,
    risk_metrics JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Market data cache for performance
CREATE TABLE IF NOT EXISTS trading.market_data (
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price DECIMAL(20, 8),
    high_price DECIMAL(20, 8),
    low_price DECIMAL(20, 8),
    close_price DECIMAL(20, 8),
    volume BIGINT,
    adj_close DECIMAL(20, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, timestamp)
);

-- Risk management table
CREATE TABLE IF NOT EXISTS trading.risk_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    risk_metrics JSONB,
    action_taken TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Positions indexes
CREATE INDEX IF NOT EXISTS idx_positions_account_symbol ON trading.positions(account_id, symbol);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON trading.positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON trading.positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_updated_at ON trading.positions(updated_at);

-- Trades indexes
CREATE INDEX IF NOT EXISTS idx_trades_account_symbol ON trading.trades(account_id, symbol);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trading.trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_execution_time ON trading.trades(execution_time);
CREATE INDEX IF NOT EXISTS idx_trades_position_id ON trading.trades(position_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trading.trades(strategy_name);

-- Portfolio summary indexes
CREATE INDEX IF NOT EXISTS idx_portfolio_summary_account ON trading.portfolio_summary(account_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_summary_timestamp ON trading.portfolio_summary(timestamp);

-- Market data indexes
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON trading.market_data(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON trading.market_data(timestamp DESC);

-- Risk events indexes
CREATE INDEX IF NOT EXISTS idx_risk_events_account ON trading.risk_events(account_id);
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON trading.risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON trading.risk_events(severity);
CREATE INDEX IF NOT EXISTS idx_risk_events_created_at ON trading.risk_events(created_at);

-- =============================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- =============================================

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers
CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON trading.accounts
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON trading.positions
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- =============================================
-- VIEWS FOR COMMON QUERIES
-- =============================================

-- Current positions view
CREATE OR REPLACE VIEW trading.current_positions AS
SELECT
    p.*,
    a.account_name,
    (p.market_value - (p.quantity * p.avg_cost)) as unrealized_pnl_calculated,
    (p.market_value / NULLIF(p.quantity * p.avg_cost, 0) - 1) * 100 as unrealized_pnl_percent
FROM trading.positions p
JOIN trading.accounts a ON p.account_id = a.account_id
WHERE p.status = 'OPEN' AND p.quantity != 0;

-- Portfolio performance view
CREATE OR REPLACE VIEW trading.portfolio_performance AS
SELECT
    ps.*,
    a.account_name,
    ps.total_pnl / NULLIF(a.initial_capital, 0) * 100 as total_return_percent,
    ps.day_pnl / NULLIF(ps.total_value - ps.day_pnl, 0) * 100 as day_return_percent
FROM trading.portfolio_summary ps
JOIN trading.accounts a ON ps.account_id = a.account_id;

-- =============================================
-- SAMPLE DATA
-- =============================================

-- Insert sample account if none exists
INSERT INTO trading.accounts (account_name, account_type, initial_capital, current_balance)
SELECT 'Demo Trading Account', 'DEMO', 100000.00, 100000.00
WHERE NOT EXISTS (SELECT 1 FROM trading.accounts WHERE account_name = 'Demo Trading Account');

-- Grant permissions (adjust as needed)
GRANT USAGE ON SCHEMA trading TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA trading TO PUBLIC;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA trading TO PUBLIC;

-- =============================================
-- PERFORMANCE OPTIMIZATIONS
-- =============================================

-- Analyze tables for better query planning
ANALYZE trading.accounts;
ANALYZE trading.positions;
ANALYZE trading.trades;
ANALYZE trading.portfolio_summary;
ANALYZE trading.market_data;