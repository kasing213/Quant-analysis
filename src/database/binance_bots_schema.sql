-- PostgreSQL Schema for Binance Trading Bots
-- Persistence for bot configuration, trades, and performance metrics

-- Create schema for Binance bots if not exists
CREATE SCHEMA IF NOT EXISTS binance;

-- ===================================
-- BOT CONFIGURATION AND STATE
-- ===================================

-- Bot configurations table
CREATE TABLE IF NOT EXISTS binance.bot_configs (
    bot_id VARCHAR(100) PRIMARY KEY,
    bot_name VARCHAR(200) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_params JSONB NOT NULL,
    interval VARCHAR(10) NOT NULL DEFAULT '1m',
    capital DECIMAL(15,2) NOT NULL DEFAULT 1000,
    position_size DECIMAL(15,2) NOT NULL,
    risk_per_trade DECIMAL(6,4) NOT NULL DEFAULT 0.0200 CHECK (risk_per_trade >= 0 AND risk_per_trade <= 1),
    max_position_size DECIMAL(6,4) NOT NULL DEFAULT 0.1000 CHECK (max_position_size >= 0 AND max_position_size <= 1),
    stop_loss_pct DECIMAL(5,2),
    take_profit_pct DECIMAL(5,2),
    trailing_stop_pct DECIMAL(6,4) CHECK (trailing_stop_pct IS NULL OR (trailing_stop_pct >= 0 AND trailing_stop_pct <= 1)),
    drawdown_guard_pct DECIMAL(6,4) CHECK (drawdown_guard_pct IS NULL OR (drawdown_guard_pct >= 0 AND drawdown_guard_pct <= 1)),
    is_active BOOLEAN DEFAULT TRUE,
    is_running BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_started_at TIMESTAMP WITH TIME ZONE,
    last_stopped_at TIMESTAMP WITH TIME ZONE
);

-- Bot state snapshots (for restart resilience)
CREATE TABLE IF NOT EXISTS binance.bot_states (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(100) NOT NULL REFERENCES binance.bot_configs(bot_id) ON DELETE CASCADE,
    state_data JSONB NOT NULL, -- Current bot state (position, indicators, etc.)
    total_pnl DECIMAL(15,2) DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    current_position_side VARCHAR(10), -- 'LONG', 'SHORT', NULL
    current_position_size DECIMAL(15,4),
    current_position_entry_price DECIMAL(12,4),
    current_trailing_stop DECIMAL(12,4),
    peak_equity DECIMAL(15,2),
    current_drawdown_pct DECIMAL(6,4),
    trading_halted BOOLEAN DEFAULT FALSE,
    halt_reason TEXT,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ===================================
-- BOT TRADES
-- ===================================

-- Binance bot trades (all executed trades from bots)
CREATE TABLE IF NOT EXISTS binance.bot_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(100) NOT NULL REFERENCES binance.bot_configs(bot_id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    order_id VARCHAR(100),
    external_order_id VARCHAR(100), -- Binance order ID
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(12,4) NOT NULL,
    trade_value DECIMAL(15,2) GENERATED ALWAYS AS (quantity * price) STORED,
    commission DECIMAL(10,4) DEFAULT 0,
    commission_asset VARCHAR(10),
    pnl DECIMAL(15,2),
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    strategy_signal VARCHAR(50), -- Entry/exit signal
    signal_reason TEXT, -- Strategy reasoning
    is_entry BOOLEAN DEFAULT TRUE,
    is_test_mode BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ===================================
-- BOT PERFORMANCE METRICS
-- ===================================

-- Daily bot performance snapshots
CREATE TABLE IF NOT EXISTS binance.bot_performance_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(100) NOT NULL REFERENCES binance.bot_configs(bot_id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_pnl DECIMAL(15,2) DEFAULT 0,
    daily_pnl DECIMAL(15,2) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0,
    avg_win DECIMAL(15,2),
    avg_loss DECIMAL(15,2),
    profit_factor DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    largest_win DECIMAL(15,2),
    largest_loss DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bot_id, snapshot_date)
);

-- Real-time bot metrics (for monitoring)
CREATE TABLE IF NOT EXISTS binance.bot_metrics_realtime (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(100) NOT NULL REFERENCES binance.bot_configs(bot_id) ON DELETE CASCADE,
    metric_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    current_price DECIMAL(12,4),
    position_size DECIMAL(15,4),
    position_value DECIMAL(15,2),
    unrealized_pnl DECIMAL(15,2),
    realized_pnl DECIMAL(15,2),
    total_pnl DECIMAL(15,2),
    strategy_indicators JSONB, -- RSI, MACD, etc.
    market_conditions JSONB -- Volatility, trend, etc.
);

-- ===================================
-- BOT SIGNALS AND DECISIONS
-- ===================================

-- Bot trading signals history (for analysis)
CREATE TABLE IF NOT EXISTS binance.bot_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(100) NOT NULL REFERENCES binance.bot_configs(bot_id) ON DELETE CASCADE,
    signal_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    signal_type VARCHAR(20) NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    signal_strength DECIMAL(5,2), -- 0-100 confidence
    indicators JSONB, -- Indicator values at signal time
    price_at_signal DECIMAL(12,4),
    action_taken VARCHAR(20), -- 'EXECUTED', 'IGNORED', 'REJECTED'
    rejection_reason TEXT,
    trade_id UUID REFERENCES binance.bot_trades(trade_id)
);

-- ===================================
-- INDEXES FOR PERFORMANCE
-- ===================================

-- Bot configs indexes
CREATE INDEX IF NOT EXISTS idx_bot_configs_active ON binance.bot_configs(is_active, is_running);
CREATE INDEX IF NOT EXISTS idx_bot_configs_symbol ON binance.bot_configs(symbol);

-- Bot states indexes
CREATE INDEX IF NOT EXISTS idx_bot_states_bot_time ON binance.bot_states(bot_id, snapshot_time DESC);

-- Bot trades indexes
CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_time ON binance.bot_trades(bot_id, execution_time DESC);
CREATE INDEX IF NOT EXISTS idx_bot_trades_symbol_time ON binance.bot_trades(symbol, execution_time);
CREATE INDEX IF NOT EXISTS idx_bot_trades_external_order ON binance.bot_trades(external_order_id);

-- Bot performance indexes
CREATE INDEX IF NOT EXISTS idx_bot_perf_bot_date ON binance.bot_performance_snapshots(bot_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_bot_metrics_bot_time ON binance.bot_metrics_realtime(bot_id, metric_time DESC);

-- Bot signals indexes
CREATE INDEX IF NOT EXISTS idx_bot_signals_bot_time ON binance.bot_signals(bot_id, signal_time DESC);
CREATE INDEX IF NOT EXISTS idx_bot_signals_type ON binance.bot_signals(signal_type, signal_time);

-- ===================================
-- VIEWS FOR COMMON QUERIES
-- ===================================

-- Current bot status view
CREATE OR REPLACE VIEW binance.bot_status_view AS
SELECT
    bc.bot_id,
    bc.bot_name,
    bc.symbol,
    bc.strategy_name,
    bc.capital,
    bc.position_size,
    bc.risk_per_trade,
    bc.max_position_size,
    bc.trailing_stop_pct,
    bc.drawdown_guard_pct,
    bc.is_active,
    bc.is_running,
    bs.total_pnl,
    bs.win_rate,
    bs.total_trades,
    bs.current_position_side,
    bs.current_position_size,
    bs.current_position_entry_price,
    bs.current_trailing_stop,
    bs.peak_equity,
    bs.current_drawdown_pct,
    bs.trading_halted,
    bs.halt_reason,
    bc.last_started_at,
    bc.last_stopped_at,
    bs.snapshot_time as last_state_update
FROM binance.bot_configs bc
LEFT JOIN LATERAL (
    SELECT *
    FROM binance.bot_states
    WHERE bot_id = bc.bot_id
    ORDER BY snapshot_time DESC
    LIMIT 1
) bs ON TRUE;

-- Bot performance summary view
CREATE OR REPLACE VIEW binance.bot_performance_summary AS
SELECT
    bc.bot_id,
    bc.bot_name,
    bc.symbol,
    bc.strategy_name,
    bc.capital,
    bc.risk_per_trade,
    bc.max_position_size,
    bc.trailing_stop_pct,
    bc.drawdown_guard_pct,
    latest_state.current_drawdown_pct,
    latest_state.trading_halted,
    latest_state.halt_reason,
    COUNT(bt.trade_id) as total_trades,
    COUNT(CASE WHEN bt.pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN bt.pnl < 0 THEN 1 END) as losing_trades,
    ROUND(100.0 * COUNT(CASE WHEN bt.pnl > 0 THEN 1 END) / NULLIF(COUNT(bt.trade_id), 0), 2) as win_rate,
    SUM(bt.pnl) as total_pnl,
    AVG(CASE WHEN bt.pnl > 0 THEN bt.pnl END) as avg_win,
    AVG(CASE WHEN bt.pnl < 0 THEN bt.pnl END) as avg_loss,
    MAX(bt.pnl) as largest_win,
    MIN(bt.pnl) as largest_loss,
    SUM(bt.commission) as total_commissions
FROM binance.bot_configs bc
LEFT JOIN binance.bot_trades bt ON bc.bot_id = bt.bot_id
LEFT JOIN LATERAL (
    SELECT
        current_drawdown_pct,
        trading_halted,
        halt_reason
    FROM binance.bot_states
    WHERE bot_id = bc.bot_id
    ORDER BY snapshot_time DESC
    LIMIT 1
) latest_state ON TRUE
GROUP BY bc.bot_id, bc.bot_name, bc.symbol, bc.strategy_name,
    bc.capital, bc.risk_per_trade, bc.max_position_size,
    bc.trailing_stop_pct, bc.drawdown_guard_pct,
    latest_state.current_drawdown_pct, latest_state.trading_halted, latest_state.halt_reason;

-- Recent bot signals view
CREATE OR REPLACE VIEW binance.recent_bot_signals AS
SELECT
    bs.bot_id,
    bc.bot_name,
    bs.signal_time,
    bs.signal_type,
    bs.signal_strength,
    bs.price_at_signal,
    bs.action_taken,
    bs.rejection_reason,
    bt.trade_id IS NOT NULL as was_executed
FROM binance.bot_signals bs
JOIN binance.bot_configs bc ON bs.bot_id = bc.bot_id
LEFT JOIN binance.bot_trades bt ON bs.trade_id = bt.trade_id
WHERE bs.signal_time > NOW() - INTERVAL '24 hours'
ORDER BY bs.signal_time DESC;

-- ===================================
-- TRIGGERS FOR DATA INTEGRITY
-- ===================================

-- Update timestamps trigger for bot configs
CREATE OR REPLACE FUNCTION binance.update_bot_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_bot_config_timestamp
BEFORE UPDATE ON binance.bot_configs
FOR EACH ROW
EXECUTE FUNCTION binance.update_bot_config_timestamp();

-- Auto-calculate win rate on bot state update
CREATE OR REPLACE FUNCTION binance.calculate_bot_win_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_trades > 0 THEN
        NEW.win_rate = ROUND(100.0 * NEW.winning_trades / NEW.total_trades, 2);
    ELSE
        NEW.win_rate = 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_win_rate_before_insert
BEFORE INSERT OR UPDATE ON binance.bot_states
FOR EACH ROW
EXECUTE FUNCTION binance.calculate_bot_win_rate();

-- ===================================
-- FUNCTIONS FOR BOT OPERATIONS
-- ===================================

-- Function to create or update bot configuration
CREATE OR REPLACE FUNCTION binance.upsert_bot_config(
    p_bot_id VARCHAR(100),
    p_bot_name VARCHAR(200),
    p_symbol VARCHAR(20),
    p_strategy_name VARCHAR(100),
    p_strategy_params JSONB,
    p_interval VARCHAR(10),
    p_capital DECIMAL(15,2),
    p_position_size DECIMAL(15,2),
    p_risk_per_trade DECIMAL(6,4),
    p_max_position_size DECIMAL(6,4),
    p_stop_loss_pct DECIMAL(5,2),
    p_take_profit_pct DECIMAL(5,2),
    p_trailing_stop_pct DECIMAL(6,4),
    p_drawdown_guard_pct DECIMAL(6,4)
)
RETURNS VARCHAR(100) AS $$
BEGIN
    INSERT INTO binance.bot_configs (
        bot_id,
        bot_name,
        symbol,
        strategy_name,
        strategy_params,
        interval,
        capital,
        position_size,
        risk_per_trade,
        max_position_size,
        stop_loss_pct,
        take_profit_pct,
        trailing_stop_pct,
        drawdown_guard_pct
    )
    VALUES (
        p_bot_id,
        p_bot_name,
        p_symbol,
        p_strategy_name,
        p_strategy_params,
        p_interval,
        p_capital,
        p_position_size,
        p_risk_per_trade,
        p_max_position_size,
        p_stop_loss_pct,
        p_take_profit_pct,
        p_trailing_stop_pct,
        p_drawdown_guard_pct
    )
    ON CONFLICT (bot_id) DO UPDATE SET
        bot_name = EXCLUDED.bot_name,
        symbol = EXCLUDED.symbol,
        strategy_name = EXCLUDED.strategy_name,
        strategy_params = EXCLUDED.strategy_params,
        interval = EXCLUDED.interval,
        capital = EXCLUDED.capital,
        position_size = EXCLUDED.position_size,
        risk_per_trade = EXCLUDED.risk_per_trade,
        max_position_size = EXCLUDED.max_position_size,
        stop_loss_pct = EXCLUDED.stop_loss_pct,
        take_profit_pct = EXCLUDED.take_profit_pct,
        trailing_stop_pct = EXCLUDED.trailing_stop_pct,
        drawdown_guard_pct = EXCLUDED.drawdown_guard_pct,
        updated_at = CURRENT_TIMESTAMP;

    RETURN p_bot_id;
END;
$$ LANGUAGE plpgsql;

-- Function to save bot state snapshot
CREATE OR REPLACE FUNCTION binance.save_bot_state(
    p_bot_id VARCHAR(100),
    p_state_data JSONB,
    p_total_pnl DECIMAL(15,2),
    p_win_rate DECIMAL(5,2),
    p_total_trades INTEGER,
    p_winning_trades INTEGER,
    p_losing_trades INTEGER,
    p_position_side VARCHAR(10),
    p_position_size DECIMAL(15,4),
    p_position_entry_price DECIMAL(12,4),
    p_current_trailing_stop DECIMAL(12,4),
    p_peak_equity DECIMAL(15,2),
    p_current_drawdown_pct DECIMAL(6,4),
    p_trading_halted BOOLEAN,
    p_halt_reason TEXT
)
RETURNS UUID AS $$
DECLARE
    v_state_id UUID;
BEGIN
    INSERT INTO binance.bot_states (
        bot_id,
        state_data,
        total_pnl,
        win_rate,
        total_trades,
        winning_trades,
        losing_trades,
        current_position_side,
        current_position_size,
        current_position_entry_price,
        current_trailing_stop,
        peak_equity,
        current_drawdown_pct,
        trading_halted,
        halt_reason
    )
    VALUES (
        p_bot_id,
        p_state_data,
        p_total_pnl,
        p_win_rate,
        p_total_trades,
        p_winning_trades,
        p_losing_trades,
        p_position_side,
        p_position_size,
        p_position_entry_price,
        p_current_trailing_stop,
        p_peak_equity,
        p_current_drawdown_pct,
        p_trading_halted,
        p_halt_reason
    )
    RETURNING state_id INTO v_state_id;

    RETURN v_state_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get latest bot state
CREATE OR REPLACE FUNCTION binance.get_latest_bot_state(p_bot_id VARCHAR(100))
RETURNS TABLE (
    state_id UUID,
    state_data JSONB,
    total_pnl DECIMAL(15,2),
    win_rate DECIMAL(5,2),
    total_trades INTEGER,
    current_position_side VARCHAR(10),
    current_position_size DECIMAL(15,4),
    current_position_entry_price DECIMAL(12,4),
    current_trailing_stop DECIMAL(12,4),
    peak_equity DECIMAL(15,2),
    current_drawdown_pct DECIMAL(6,4),
    trading_halted BOOLEAN,
    halt_reason TEXT,
    snapshot_time TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        bs.state_id,
        bs.state_data,
        bs.total_pnl,
        bs.win_rate,
        bs.total_trades,
        bs.current_position_side,
        bs.current_position_size,
        bs.current_position_entry_price,
        bs.current_trailing_stop,
        bs.peak_equity,
        bs.current_drawdown_pct,
        bs.trading_halted,
        bs.halt_reason,
        bs.snapshot_time
    FROM binance.bot_states bs
    WHERE bs.bot_id = p_bot_id
    ORDER BY bs.snapshot_time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to record bot trade
CREATE OR REPLACE FUNCTION binance.record_bot_trade(
    p_bot_id VARCHAR(100),
    p_symbol VARCHAR(20),
    p_order_id VARCHAR(100),
    p_external_order_id VARCHAR(100),
    p_side VARCHAR(10),
    p_order_type VARCHAR(20),
    p_quantity DECIMAL(15,4),
    p_price DECIMAL(12,4),
    p_commission DECIMAL(10,4),
    p_commission_asset VARCHAR(10),
    p_pnl DECIMAL(15,2),
    p_strategy_signal VARCHAR(50),
    p_signal_reason TEXT,
    p_is_entry BOOLEAN,
    p_is_test_mode BOOLEAN
)
RETURNS UUID AS $$
DECLARE
    v_trade_id UUID;
BEGIN
    INSERT INTO binance.bot_trades (
        bot_id, symbol, order_id, external_order_id, side, order_type,
        quantity, price, commission, commission_asset, pnl,
        strategy_signal, signal_reason, is_entry, is_test_mode
    )
    VALUES (
        p_bot_id, p_symbol, p_order_id, p_external_order_id, p_side, p_order_type,
        p_quantity, p_price, p_commission, p_commission_asset, p_pnl,
        p_strategy_signal, p_signal_reason, p_is_entry, p_is_test_mode
    )
    RETURNING trade_id INTO v_trade_id;

    RETURN v_trade_id;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old metrics (keep last 90 days)
CREATE OR REPLACE FUNCTION binance.cleanup_old_metrics()
RETURNS void AS $$
BEGIN
    DELETE FROM binance.bot_metrics_realtime
    WHERE metric_time < NOW() - INTERVAL '90 days';

    DELETE FROM binance.bot_signals
    WHERE signal_time < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed)
-- GRANT ALL ON SCHEMA binance TO trader;
-- GRANT ALL ON ALL TABLES IN SCHEMA binance TO trader;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA binance TO trader;
