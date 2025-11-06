-- PostgreSQL Schema for Quantitative Trading System
-- Optimized for high-frequency data queries and analytical workloads

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create schemas for organization
CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS backtesting;

-- ===================================
-- TRADING SCHEMA - Core Trading Data
-- ===================================

-- Accounts table for multi-account support
CREATE TABLE trading.accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('PAPER', 'LIVE', 'DEMO')),
    broker VARCHAR(50) NOT NULL DEFAULT 'IB',
    initial_capital DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Account balances with history
CREATE TABLE trading.account_balances (
    balance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    cash_balance DECIMAL(15,2) NOT NULL,
    total_equity DECIMAL(15,2) NOT NULL,
    buying_power DECIMAL(15,2),
    day_pnl DECIMAL(15,2) DEFAULT 0,
    unrealized_pnl DECIMAL(15,2) DEFAULT 0,
    realized_pnl DECIMAL(15,2) DEFAULT 0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(20) DEFAULT 'SYSTEM'
);

-- Symbols master table with metadata
CREATE TABLE trading.symbols (
    symbol_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    company_name VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(200),
    exchange VARCHAR(20),
    currency VARCHAR(3) DEFAULT 'USD',
    security_type VARCHAR(20) DEFAULT 'STK' CHECK (security_type IN ('STK', 'OPT', 'FUT', 'CASH', 'BOND')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Trades table - all executed trades
CREATE TABLE trading.trades (
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL', 'SHORT', 'COVER')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price DECIMAL(12,4) NOT NULL CHECK (price > 0),
    trade_value DECIMAL(15,2) GENERATED ALWAYS AS (quantity * price) STORED,
    commission DECIMAL(8,2) DEFAULT 0,
    net_value DECIMAL(15,2) GENERATED ALWAYS AS (
        CASE
            WHEN side IN ('BUY', 'COVER') THEN -(quantity * price + commission)
            ELSE (quantity * price - commission)
        END
    ) STORED,
    order_id VARCHAR(50),
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    settlement_date DATE,
    strategy_name VARCHAR(100),
    notes TEXT,
    data_source VARCHAR(20) DEFAULT 'SYSTEM',
    external_trade_id VARCHAR(100)
);

-- Positions table - current and historical positions
CREATE TABLE trading.positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL, -- Can be negative for short positions
    avg_price DECIMAL(12,4) NOT NULL CHECK (avg_price > 0),
    current_price DECIMAL(12,4),
    market_value DECIMAL(15,2) GENERATED ALWAYS AS (quantity * current_price) STORED,
    unrealized_pnl DECIMAL(15,2) GENERATED ALWAYS AS (quantity * (current_price - avg_price)) STORED,
    unrealized_pnl_pct DECIMAL(8,4) GENERATED ALWAYS AS (
        CASE WHEN avg_price > 0 THEN ((current_price / avg_price) - 1) * 100 ELSE 0 END
    ) STORED,
    position_date DATE DEFAULT CURRENT_DATE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Orders table for order management and history
CREATE TABLE trading.orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    time_in_force VARCHAR(10) DEFAULT 'DAY' CHECK (time_in_force IN ('DAY', 'GTC', 'IOC', 'FOK')),
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'FILLED', 'PARTIAL', 'CANCELLED', 'REJECTED')),
    filled_quantity INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(12,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP WITH TIME ZONE,
    external_order_id VARCHAR(100),
    strategy_name VARCHAR(100),
    parent_order_id UUID REFERENCES trading.orders(order_id)
);

-- ==========================================
-- MARKET DATA SCHEMA - Price and Market Data
-- ==========================================

-- Historical price data optimized for time-series queries
CREATE TABLE market_data.daily_prices (
    price_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    price_date DATE NOT NULL,
    open_price DECIMAL(12,4) NOT NULL,
    high_price DECIMAL(12,4) NOT NULL,
    low_price DECIMAL(12,4) NOT NULL,
    close_price DECIMAL(12,4) NOT NULL,
    adjusted_close DECIMAL(12,4),
    volume BIGINT DEFAULT 0,
    dividend DECIMAL(8,4) DEFAULT 0,
    split_factor DECIMAL(8,4) DEFAULT 1,
    data_source VARCHAR(20) DEFAULT 'YAHOO',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, price_date)
);

-- Intraday price data for high-frequency analysis
CREATE TABLE market_data.intraday_prices (
    price_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    price DECIMAL(12,4) NOT NULL,
    volume INTEGER DEFAULT 0,
    bid DECIMAL(12,4),
    ask DECIMAL(12,4),
    data_source VARCHAR(20) DEFAULT 'IB'
) PARTITION BY RANGE (timestamp);

-- Real-time market data snapshots
CREATE TABLE market_data.market_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    last_price DECIMAL(12,4) NOT NULL,
    bid DECIMAL(12,4),
    ask DECIMAL(12,4),
    bid_size INTEGER,
    ask_size INTEGER,
    volume BIGINT DEFAULT 0,
    day_high DECIMAL(12,4),
    day_low DECIMAL(12,4),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(20) DEFAULT 'IB'
);

-- =====================================
-- ANALYTICS SCHEMA - Performance Metrics
-- =====================================

-- Portfolio performance snapshots
CREATE TABLE analytics.portfolio_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    snapshot_date DATE NOT NULL,
    total_equity DECIMAL(15,2) NOT NULL,
    cash_balance DECIMAL(15,2) NOT NULL,
    positions_value DECIMAL(15,2) NOT NULL,
    day_pnl DECIMAL(15,2) DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0,
    total_return_pct DECIMAL(8,4) DEFAULT 0,
    num_positions INTEGER DEFAULT 0,
    largest_position_pct DECIMAL(8,4) DEFAULT 0,
    sharpe_ratio DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    volatility DECIMAL(8,4),
    beta DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, snapshot_date)
);

-- Risk metrics and analytics
CREATE TABLE analytics.risk_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    metric_date DATE NOT NULL,
    var_95 DECIMAL(12,4), -- Value at Risk 95%
    var_99 DECIMAL(12,4), -- Value at Risk 99%
    expected_shortfall DECIMAL(12,4),
    portfolio_beta DECIMAL(8,4),
    portfolio_volatility DECIMAL(8,4),
    concentration_ratio DECIMAL(8,4), -- Largest position as % of portfolio
    correlation_spy DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ======================================
-- BACKTESTING SCHEMA - Strategy Analysis
-- ======================================

-- Backtesting runs and configurations
CREATE TABLE backtesting.backtest_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_name VARCHAR(200) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    strategy_params JSONB, -- Store strategy parameters as JSON
    run_status VARCHAR(20) DEFAULT 'PENDING' CHECK (run_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_time_seconds INTEGER
);

-- Backtesting performance results
CREATE TABLE backtesting.backtest_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES backtesting.backtest_runs(run_id) ON DELETE CASCADE,
    total_return DECIMAL(8,4),
    total_return_pct DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    volatility DECIMAL(8,4),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    avg_win DECIMAL(12,2),
    avg_loss DECIMAL(12,2),
    profit_factor DECIMAL(8,4),
    starting_value DECIMAL(15,2),
    ending_value DECIMAL(15,2),
    benchmark_return DECIMAL(8,4), -- SPY return for comparison
    alpha DECIMAL(8,4),
    beta DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Individual backtest trades
CREATE TABLE backtesting.backtest_trades (
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES backtesting.backtest_runs(run_id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12,4) NOT NULL,
    exit_price DECIMAL(12,4),
    entry_date DATE NOT NULL,
    exit_date DATE,
    pnl DECIMAL(12,2),
    pnl_pct DECIMAL(8,4),
    holding_period_days INTEGER,
    commission DECIMAL(8,2) DEFAULT 0,
    trade_reason VARCHAR(100) -- Entry/exit signal reason
);

-- ===========================
-- INDEXES FOR PERFORMANCE
-- ===========================

-- Trading schema indexes
CREATE INDEX idx_trades_account_symbol_time ON trading.trades(account_id, symbol, execution_time);
CREATE INDEX idx_trades_symbol_time ON trading.trades(symbol, execution_time);
CREATE INDEX idx_trades_execution_time ON trading.trades(execution_time);
CREATE INDEX idx_positions_account_symbol ON trading.positions(account_id, symbol) WHERE is_active = TRUE;
CREATE INDEX idx_account_balances_account_time ON trading.account_balances(account_id, timestamp);

-- Market data indexes
CREATE INDEX idx_daily_prices_symbol_date ON market_data.daily_prices(symbol, price_date);
CREATE INDEX idx_daily_prices_date ON market_data.daily_prices(price_date);
CREATE INDEX idx_market_snapshots_symbol_time ON market_data.market_snapshots(symbol, timestamp);

-- Analytics indexes
CREATE INDEX idx_portfolio_snapshots_account_date ON analytics.portfolio_snapshots(account_id, snapshot_date);
CREATE INDEX idx_risk_metrics_account_date ON analytics.risk_metrics(account_id, metric_date);

-- Backtesting indexes
CREATE INDEX idx_backtest_runs_strategy ON backtesting.backtest_runs(strategy_name, created_at);
CREATE INDEX idx_backtest_trades_run_symbol ON backtesting.backtest_trades(run_id, symbol);

-- ===========================
-- PARTITIONING FOR SCALABILITY
-- ===========================

-- Create monthly partitions for intraday prices (example for current and next months)
CREATE TABLE market_data.intraday_prices_y2024m09 PARTITION OF market_data.intraday_prices
FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');

CREATE TABLE market_data.intraday_prices_y2024m10 PARTITION OF market_data.intraday_prices
FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

-- ===========================
-- VIEWS FOR COMMON QUERIES
-- ===========================

-- Current portfolio view
CREATE VIEW analytics.current_portfolio AS
SELECT
    p.account_id,
    p.symbol,
    p.quantity,
    p.avg_price,
    p.current_price,
    p.market_value,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    s.company_name,
    s.sector,
    s.industry
FROM trading.positions p
LEFT JOIN trading.symbols s ON p.symbol = s.symbol
WHERE p.is_active = TRUE AND p.quantity != 0;

-- Daily portfolio performance view
CREATE VIEW analytics.daily_portfolio_performance AS
SELECT
    ps.account_id,
    ps.snapshot_date,
    ps.total_equity,
    ps.total_pnl,
    ps.total_return_pct,
    LAG(ps.total_equity) OVER (PARTITION BY ps.account_id ORDER BY ps.snapshot_date) as prev_equity,
    (ps.total_equity - LAG(ps.total_equity) OVER (PARTITION BY ps.account_id ORDER BY ps.snapshot_date)) as daily_change
FROM analytics.portfolio_snapshots ps
ORDER BY ps.account_id, ps.snapshot_date;

-- Top performing strategies view
CREATE VIEW backtesting.top_strategies AS
SELECT
    br.strategy_name,
    COUNT(*) as total_runs,
    AVG(res.total_return_pct) as avg_return,
    AVG(res.sharpe_ratio) as avg_sharpe,
    AVG(res.max_drawdown) as avg_drawdown,
    AVG(res.win_rate) as avg_win_rate
FROM backtesting.backtest_runs br
JOIN backtesting.backtest_results res ON br.run_id = res.run_id
WHERE br.run_status = 'COMPLETED'
GROUP BY br.strategy_name
ORDER BY avg_return DESC;

-- ===========================
-- TRIGGERS FOR DATA INTEGRITY
-- ===========================

-- Update timestamps trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to relevant tables
CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON trading.accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON trading.positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Position validation trigger
CREATE OR REPLACE FUNCTION validate_position_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure current_price is positive if set
    IF NEW.current_price IS NOT NULL AND NEW.current_price <= 0 THEN
        RAISE EXCEPTION 'Current price must be positive';
    END IF;

    -- Update last_updated timestamp
    NEW.last_updated = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER validate_position_before_insert_update
    BEFORE INSERT OR UPDATE ON trading.positions
    FOR EACH ROW EXECUTE FUNCTION validate_position_data();

-- ===========================
-- FUNCTIONS FOR COMMON OPERATIONS
-- ===========================

-- Function to get portfolio summary
CREATE OR REPLACE FUNCTION analytics.get_portfolio_summary(account_uuid UUID)
RETURNS TABLE (
    total_equity DECIMAL(15,2),
    cash_balance DECIMAL(15,2),
    positions_value DECIMAL(15,2),
    total_pnl DECIMAL(15,2),
    num_positions BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ab.total_equity,
        ab.cash_balance,
        COALESCE(SUM(p.market_value), 0) as positions_value,
        COALESCE(SUM(p.unrealized_pnl), 0) as total_pnl,
        COUNT(p.position_id) as num_positions
    FROM trading.account_balances ab
    LEFT JOIN trading.positions p ON ab.account_id = p.account_id AND p.is_active = TRUE
    WHERE ab.account_id = account_uuid
        AND ab.timestamp = (
            SELECT MAX(timestamp)
            FROM trading.account_balances
            WHERE account_id = account_uuid
        )
    GROUP BY ab.total_equity, ab.cash_balance;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate portfolio metrics
CREATE OR REPLACE FUNCTION analytics.calculate_sharpe_ratio(
    account_uuid UUID,
    days_back INTEGER DEFAULT 252
)
RETURNS DECIMAL(8,4) AS $$
DECLARE
    sharpe_result DECIMAL(8,4);
BEGIN
    WITH daily_returns AS (
        SELECT
            snapshot_date,
            total_return_pct,
            LAG(total_return_pct) OVER (ORDER BY snapshot_date) as prev_return
        FROM analytics.portfolio_snapshots
        WHERE account_id = account_uuid
            AND snapshot_date >= CURRENT_DATE - INTERVAL '%s days' % days_back
    ),
    return_stats AS (
        SELECT
            AVG(total_return_pct - prev_return) as avg_return,
            STDDEV(total_return_pct - prev_return) as return_stddev
        FROM daily_returns
        WHERE prev_return IS NOT NULL
    )
    SELECT
        CASE
            WHEN return_stddev > 0 THEN (avg_return * SQRT(252)) / (return_stddev * SQRT(252))
            ELSE NULL
        END
    INTO sharpe_result
    FROM return_stats;

    RETURN sharpe_result;
END;
$$ LANGUAGE plpgsql;