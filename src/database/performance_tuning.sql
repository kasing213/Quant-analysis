-- PostgreSQL Performance Optimizations for Quantitative Trading Workloads
-- This script contains performance tuning settings and optimizations

-- ===========================
-- DATABASE CONFIGURATION
-- ===========================

-- Memory settings for analytical workloads
-- Adjust based on available RAM (these are for 8GB+ systems)
ALTER SYSTEM SET shared_buffers = '2GB';                    -- 25% of RAM
ALTER SYSTEM SET effective_cache_size = '6GB';              -- 75% of RAM
ALTER SYSTEM SET work_mem = '256MB';                        -- Per-operation memory
ALTER SYSTEM SET maintenance_work_mem = '512MB';            -- For maintenance operations

-- Connection settings
ALTER SYSTEM SET max_connections = 100;                     -- Reasonable for analytical workload
ALTER SYSTEM SET max_prepared_transactions = 50;

-- Write-ahead logging optimization
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET checkpoint_timeout = '15min';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET min_wal_size = '1GB';

-- Query planner settings for analytical queries
ALTER SYSTEM SET random_page_cost = 1.1;                    -- SSD optimization
ALTER SYSTEM SET seq_page_cost = 1.0;
ALTER SYSTEM SET cpu_tuple_cost = 0.01;
ALTER SYSTEM SET cpu_index_tuple_cost = 0.005;
ALTER SYSTEM SET effective_io_concurrency = 200;           -- SSD optimization

-- Parallel query settings
ALTER SYSTEM SET max_parallel_workers = 8;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET parallel_tuple_cost = 0.1;
ALTER SYSTEM SET parallel_setup_cost = 1000.0;

-- Statistics and autovacuum
ALTER SYSTEM SET default_statistics_target = 100;          -- More detailed statistics
ALTER SYSTEM SET autovacuum_max_workers = 3;
ALTER SYSTEM SET autovacuum_naptime = '10s';               -- More frequent autovacuum

-- Apply configuration changes
SELECT pg_reload_conf();

-- ===========================
-- ADDITIONAL INDEXES FOR PERFORMANCE
-- ===========================

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_execution_time_symbol
ON trading.trades(account_id, execution_time DESC, symbol);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_account_active_symbol
ON trading.positions(account_id, is_active, symbol) WHERE is_active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_account_balances_account_timestamp_desc
ON trading.account_balances(account_id, timestamp DESC);

-- Partial indexes for better performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_buy_orders
ON trading.trades(symbol, execution_time) WHERE side = 'BUY';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_sell_orders
ON trading.trades(symbol, execution_time) WHERE side = 'SELL';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_long_active
ON trading.positions(symbol, market_value) WHERE quantity > 0 AND is_active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_short_active
ON trading.positions(symbol, market_value) WHERE quantity < 0 AND is_active = TRUE;

-- Market data indexes for time-series queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_prices_symbol_date_desc
ON market_data.daily_prices(symbol, price_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_prices_date_volume
ON market_data.daily_prices(price_date, volume) WHERE volume > 0;

-- Backtesting performance indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_strategy_symbol_date
ON backtesting.backtest_runs(strategy_name, symbol, start_date, end_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_results_performance
ON backtesting.backtest_results(total_return_pct DESC, sharpe_ratio DESC, max_drawdown ASC);

-- ===========================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ===========================

-- Portfolio performance summary (refreshed periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.portfolio_performance_summary AS
SELECT
    p.account_id,
    COUNT(p.position_id) as total_positions,
    SUM(CASE WHEN p.quantity > 0 THEN p.market_value ELSE 0 END) as long_value,
    SUM(CASE WHEN p.quantity < 0 THEN ABS(p.market_value) ELSE 0 END) as short_value,
    SUM(p.market_value) as net_value,
    SUM(p.unrealized_pnl) as total_unrealized_pnl,
    AVG(p.unrealized_pnl_pct) as avg_position_pnl_pct,
    MAX(ABS(p.market_value)) as largest_position_value,
    COUNT(DISTINCT p.symbol) as unique_symbols,
    MAX(p.last_updated) as last_calculated
FROM trading.positions p
WHERE p.is_active = TRUE AND p.quantity != 0
GROUP BY p.account_id;

CREATE UNIQUE INDEX ON analytics.portfolio_performance_summary(account_id);

-- Daily trading volume summary
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.daily_trading_summary AS
SELECT
    t.account_id,
    t.execution_time::date as trade_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN t.side = 'BUY' THEN t.quantity ELSE 0 END) as shares_bought,
    SUM(CASE WHEN t.side = 'SELL' THEN t.quantity ELSE 0 END) as shares_sold,
    SUM(CASE WHEN t.side = 'BUY' THEN t.trade_value ELSE 0 END) as buy_volume,
    SUM(CASE WHEN t.side = 'SELL' THEN t.trade_value ELSE 0 END) as sell_volume,
    SUM(t.trade_value) as total_volume,
    SUM(t.commission) as total_commissions,
    COUNT(DISTINCT t.symbol) as symbols_traded
FROM trading.trades t
GROUP BY t.account_id, t.execution_time::date;

CREATE UNIQUE INDEX ON analytics.daily_trading_summary(account_id, trade_date);

-- Top performing strategies
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.strategy_leaderboard AS
SELECT
    br.strategy_name,
    COUNT(*) as total_runs,
    AVG(res.total_return_pct) as avg_return_pct,
    STDDEV(res.total_return_pct) as return_volatility,
    AVG(res.sharpe_ratio) as avg_sharpe_ratio,
    AVG(res.max_drawdown) as avg_max_drawdown,
    AVG(res.win_rate) as avg_win_rate,
    AVG(res.total_trades) as avg_trades_per_run,
    MAX(res.total_return_pct) as best_return,
    MIN(res.max_drawdown) as best_drawdown,
    COUNT(DISTINCT br.symbol) as symbols_tested
FROM backtesting.backtest_runs br
JOIN backtesting.backtest_results res ON br.run_id = res.run_id
WHERE br.run_status = 'COMPLETED'
GROUP BY br.strategy_name;

CREATE UNIQUE INDEX ON analytics.strategy_leaderboard(strategy_name);

-- ===========================
-- FUNCTIONS FOR PERFORMANCE
-- ===========================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION analytics.refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.portfolio_performance_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.daily_trading_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.strategy_leaderboard;

    RAISE NOTICE 'All materialized views refreshed at %', CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate portfolio metrics efficiently
CREATE OR REPLACE FUNCTION analytics.calculate_portfolio_metrics(
    account_uuid UUID,
    calculation_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    total_equity DECIMAL(15,2),
    cash_balance DECIMAL(15,2),
    positions_value DECIMAL(15,2),
    unrealized_pnl DECIMAL(15,2),
    num_positions INTEGER,
    concentration_ratio DECIMAL(8,4),
    long_exposure DECIMAL(15,2),
    short_exposure DECIMAL(15,2),
    beta_estimate DECIMAL(8,4)
) AS $$
DECLARE
    total_portfolio_value DECIMAL(15,2);
    largest_position_value DECIMAL(15,2);
BEGIN
    -- Get latest account balance
    SELECT ab.total_equity, ab.cash_balance
    INTO total_equity, cash_balance
    FROM trading.account_balances ab
    WHERE ab.account_id = account_uuid
    ORDER BY ab.timestamp DESC
    LIMIT 1;

    -- Calculate position metrics
    SELECT
        COALESCE(SUM(p.market_value), 0),
        COALESCE(SUM(p.unrealized_pnl), 0),
        COUNT(*)::INTEGER,
        COALESCE(MAX(ABS(p.market_value)), 0),
        COALESCE(SUM(CASE WHEN p.quantity > 0 THEN p.market_value ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN p.quantity < 0 THEN ABS(p.market_value) ELSE 0 END), 0)
    INTO positions_value, unrealized_pnl, num_positions, largest_position_value, long_exposure, short_exposure
    FROM trading.positions p
    WHERE p.account_id = account_uuid
        AND p.is_active = TRUE
        AND p.quantity != 0;

    -- Calculate concentration ratio
    total_portfolio_value := COALESCE(total_equity, 0);
    IF total_portfolio_value > 0 THEN
        concentration_ratio := largest_position_value / total_portfolio_value;
    ELSE
        concentration_ratio := 0;
    END IF;

    -- Simplified beta calculation (would need market data for proper calculation)
    beta_estimate := 1.0; -- Placeholder

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to get top/bottom performers
CREATE OR REPLACE FUNCTION analytics.get_position_performers(
    account_uuid UUID,
    top_n INTEGER DEFAULT 5
)
RETURNS TABLE (
    symbol VARCHAR(20),
    unrealized_pnl DECIMAL(15,2),
    unrealized_pnl_pct DECIMAL(8,4),
    market_value DECIMAL(15,2),
    rank_position INTEGER
) AS $$
BEGIN
    RETURN QUERY
    (SELECT
        p.symbol,
        p.unrealized_pnl,
        p.unrealized_pnl_pct,
        p.market_value,
        ROW_NUMBER() OVER (ORDER BY p.unrealized_pnl DESC)::INTEGER
    FROM trading.positions p
    WHERE p.account_id = account_uuid
        AND p.is_active = TRUE
        AND p.quantity != 0
    ORDER BY p.unrealized_pnl DESC
    LIMIT top_n)

    UNION ALL

    (SELECT
        p.symbol,
        p.unrealized_pnl,
        p.unrealized_pnl_pct,
        p.market_value,
        ROW_NUMBER() OVER (ORDER BY p.unrealized_pnl ASC)::INTEGER + 1000 -- Offset for losers
    FROM trading.positions p
    WHERE p.account_id = account_uuid
        AND p.is_active = TRUE
        AND p.quantity != 0
    ORDER BY p.unrealized_pnl ASC
    LIMIT top_n);
END;
$$ LANGUAGE plpgsql;

-- ===========================
-- PARTITIONING FOR LARGE DATASETS
-- ===========================

-- Function to create monthly partitions for intraday_prices
CREATE OR REPLACE FUNCTION market_data.create_monthly_partition(
    year_month TEXT -- Format: 'YYYY-MM'
)
RETURNS void AS $$
DECLARE
    table_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    table_name := 'intraday_prices_y' || REPLACE(year_month, '-', 'm');
    start_date := year_month || '-01';
    end_date := (DATE(start_date) + INTERVAL '1 month')::TEXT;

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS market_data.%I PARTITION OF market_data.intraday_prices
         FOR VALUES FROM (%L) TO (%L)',
        table_name, start_date, end_date
    );

    RAISE NOTICE 'Created partition % for date range % to %', table_name, start_date, end_date;
END;
$$ LANGUAGE plpgsql;

-- ===========================
-- AUTOMATIC MAINTENANCE TASKS
-- ===========================

-- Function to cleanup old data
CREATE OR REPLACE FUNCTION maintenance.cleanup_old_data(
    days_to_keep INTEGER DEFAULT 365
)
RETURNS void AS $$
DECLARE
    cutoff_date DATE;
    deleted_count INTEGER;
BEGIN
    cutoff_date := CURRENT_DATE - INTERVAL '%s days' % days_to_keep;

    -- Cleanup old market snapshots
    DELETE FROM market_data.market_snapshots
    WHERE timestamp < cutoff_date;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % old market snapshots before %', deleted_count, cutoff_date;

    -- Cleanup old account balance records (keep monthly summaries)
    WITH monthly_keepers AS (
        SELECT DISTINCT ON (account_id, DATE_TRUNC('month', timestamp))
               balance_id
        FROM trading.account_balances
        WHERE timestamp < cutoff_date
        ORDER BY account_id, DATE_TRUNC('month', timestamp), timestamp DESC
    )
    DELETE FROM trading.account_balances ab
    WHERE ab.timestamp < cutoff_date
      AND ab.balance_id NOT IN (SELECT balance_id FROM monthly_keepers);

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % old account balance records before %', deleted_count, cutoff_date;

    -- Update statistics
    ANALYZE;

    RAISE NOTICE 'Data cleanup completed at %', CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- ===========================
-- MONITORING AND ALERTING
-- ===========================

-- View for monitoring query performance
CREATE VIEW monitoring.slow_queries AS
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
WHERE mean_time > 100 -- queries taking more than 100ms on average
ORDER BY mean_time DESC;

-- Function to check database health
CREATE OR REPLACE FUNCTION monitoring.check_database_health()
RETURNS TABLE (
    metric_name TEXT,
    metric_value TEXT,
    status TEXT
) AS $$
BEGIN
    -- Check connection count
    RETURN QUERY
    SELECT
        'active_connections'::TEXT,
        (SELECT COUNT(*)::TEXT FROM pg_stat_activity WHERE state = 'active'),
        CASE
            WHEN (SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active') > 50 THEN 'WARNING'
            ELSE 'OK'
        END;

    -- Check largest table sizes
    RETURN QUERY
    SELECT
        'largest_table'::TEXT,
        (SELECT schemaname || '.' || tablename || ' (' || pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) || ')'
         FROM pg_tables
         ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
         LIMIT 1),
        'INFO'::TEXT;

    -- Check database size
    RETURN QUERY
    SELECT
        'database_size'::TEXT,
        pg_size_pretty(pg_database_size(current_database())),
        CASE
            WHEN pg_database_size(current_database()) > 10 * 1024 * 1024 * 1024 THEN 'WARNING' -- 10GB
            ELSE 'OK'
        END;

    -- Check last autovacuum
    RETURN QUERY
    SELECT
        'last_autovacuum'::TEXT,
        COALESCE(MAX(last_autovacuum)::TEXT, 'Never') as last_vacuum,
        CASE
            WHEN MAX(last_autovacuum) < CURRENT_TIMESTAMP - INTERVAL '1 day' THEN 'WARNING'
            WHEN MAX(last_autovacuum) IS NULL THEN 'WARNING'
            ELSE 'OK'
        END
    FROM pg_stat_user_tables;

END;
$$ LANGUAGE plpgsql;

-- ===========================
-- SCHEDULED MAINTENANCE
-- ===========================

-- Note: These would typically be set up with pg_cron or external scheduler

-- Example cron jobs (requires pg_cron extension):
-- SELECT cron.schedule('refresh-materialized-views', '*/5 * * * *', 'SELECT analytics.refresh_all_materialized_views();');
-- SELECT cron.schedule('cleanup-old-data', '0 2 * * 0', 'SELECT maintenance.cleanup_old_data(365);');
-- SELECT cron.schedule('update-stats', '0 3 * * *', 'ANALYZE;');