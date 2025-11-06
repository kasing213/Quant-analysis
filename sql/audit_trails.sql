-- =============================================
-- AUDIT TRAILS AND COMPLIANCE ENHANCEMENTS
-- Production-Grade Trade Logging and Regulatory Compliance
-- =============================================

-- Set timezone to UTC for consistent time handling
SET timezone = 'UTC';

-- =============================================
-- AUDIT SCHEMA TABLES
-- =============================================

-- Comprehensive audit log for all database operations
CREATE TABLE IF NOT EXISTS audit.database_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE', 'SELECT')),
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],
    user_name VARCHAR(100) NOT NULL,
    session_id VARCHAR(100),
    application_name VARCHAR(100),
    client_ip INET,
    audit_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    transaction_id BIGINT DEFAULT txid_current(),
    row_id UUID,
    correlation_id UUID
) PARTITION BY RANGE (audit_timestamp);

-- Create monthly partitions for audit log (last 2 years + next year)
CREATE TABLE IF NOT EXISTS audit.database_audit_log_2024 PARTITION OF audit.database_audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE IF NOT EXISTS audit.database_audit_log_2025 PARTITION OF audit.database_audit_log
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE IF NOT EXISTS audit.database_audit_log_2026 PARTITION OF audit.database_audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- Immutable transaction log with cryptographic hashing
CREATE TABLE IF NOT EXISTS audit.transaction_integrity_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_hash VARCHAR(64) NOT NULL UNIQUE,
    previous_hash VARCHAR(64),
    block_number BIGINT NOT NULL,
    transaction_data JSONB NOT NULL,
    merkle_root VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_hash_format CHECK (transaction_hash ~ '^[a-f0-9]{64}$')
);

-- User session audit trail
CREATE TABLE IF NOT EXISTS audit.user_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_name VARCHAR(100) NOT NULL,
    login_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP WITH TIME ZONE,
    client_ip INET,
    user_agent TEXT,
    session_token_hash VARCHAR(64),
    mfa_verified BOOLEAN DEFAULT FALSE,
    risk_score INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'TERMINATED', 'SUSPICIOUS'))
);

-- =============================================
-- COMPLIANCE SCHEMA TABLES
-- =============================================

-- Trade reporting for regulatory compliance (MiFID II, Dodd-Frank)
CREATE TABLE IF NOT EXISTS compliance.trade_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID NOT NULL REFERENCES trading.trades(trade_id),
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('MIFID_II', 'DODD_FRANK', 'EMIR', 'CFTC')),
    reporting_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    transaction_reference_number VARCHAR(100),
    venue_of_execution VARCHAR(50),
    instrument_identification VARCHAR(50),
    price_notation VARCHAR(20),
    price_multiplier DECIMAL(10, 6),
    notional_currency VARCHAR(10),
    investment_decision_within_firm VARCHAR(100),
    execution_decision_within_firm VARCHAR(100),
    waiver_indicator VARCHAR(10),
    short_selling_indicator VARCHAR(10),
    commodity_derivative_indicator VARCHAR(10),
    submitted_to_regulator BOOLEAN DEFAULT FALSE,
    submission_timestamp TIMESTAMP WITH TIME ZONE,
    regulatory_response JSONB,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SUBMITTED', 'ACCEPTED', 'REJECTED'))
);

-- Best execution monitoring and reporting
CREATE TABLE IF NOT EXISTS compliance.best_execution_records (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID NOT NULL REFERENCES trading.trades(trade_id),
    venue_analysis JSONB NOT NULL,
    execution_factors JSONB,
    venue_performance_metrics JSONB,
    price_improvement DECIMAL(20, 8),
    market_impact DECIMAL(20, 8),
    timing_impact DECIMAL(20, 8),
    opportunity_cost DECIMAL(20, 8),
    execution_quality_score INTEGER,
    benchmark_comparison JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Position limits and risk monitoring
CREATE TABLE IF NOT EXISTS compliance.position_limits (
    limit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES trading.accounts(account_id),
    limit_type VARCHAR(50) NOT NULL CHECK (limit_type IN ('POSITION_SIZE', 'CONCENTRATION', 'SECTOR', 'COUNTRY', 'CURRENCY', 'VAR', 'LEVERAGE')),
    instrument_filter JSONB,
    limit_value DECIMAL(20, 8) NOT NULL,
    warning_threshold DECIMAL(20, 8),
    currency VARCHAR(10) DEFAULT 'USD',
    effective_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    effective_until TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'EXPIRED')),
    created_by VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    approval_timestamp TIMESTAMP WITH TIME ZONE
);

-- Compliance breaches and violations
CREATE TABLE IF NOT EXISTS compliance.compliance_breaches (
    breach_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    breach_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    affected_accounts UUID[],
    affected_trades UUID[],
    detection_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    detection_method VARCHAR(50),
    remediation_actions TEXT,
    remediation_timestamp TIMESTAMP WITH TIME ZONE,
    reported_to_regulator BOOLEAN DEFAULT FALSE,
    regulatory_reference VARCHAR(100),
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'INVESTIGATING', 'REMEDIATED', 'CLOSED')),
    assigned_to VARCHAR(100),
    resolution_notes TEXT
);

-- =============================================
-- SECURITY SCHEMA TABLES
-- =============================================

-- Access control and permissions audit
CREATE TABLE IF NOT EXISTS security.access_log (
    access_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_name VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    action VARCHAR(50) NOT NULL,
    access_granted BOOLEAN NOT NULL,
    denial_reason TEXT,
    client_ip INET,
    user_agent TEXT,
    session_id UUID REFERENCES audit.user_sessions(session_id),
    access_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    risk_factors JSONB
);

-- Data encryption and key management
CREATE TABLE IF NOT EXISTS security.encryption_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_purpose VARCHAR(50) NOT NULL,
    key_algorithm VARCHAR(50) NOT NULL,
    key_length INTEGER NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    rotated_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'ROTATED', 'COMPROMISED')),
    created_by VARCHAR(100) NOT NULL
);

-- Security incidents and monitoring
CREATE TABLE IF NOT EXISTS security.security_incidents (
    incident_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    source_ip INET,
    affected_systems TEXT[],
    detection_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolution_timestamp TIMESTAMP WITH TIME ZONE,
    investigation_notes TEXT,
    containment_actions TEXT,
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'INVESTIGATING', 'CONTAINED', 'RESOLVED')),
    assigned_analyst VARCHAR(100)
);

-- =============================================
-- REPORTING SCHEMA TABLES
-- =============================================

-- Regulatory reporting schedules and status
CREATE TABLE IF NOT EXISTS reporting.regulatory_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_type VARCHAR(50) NOT NULL,
    reporting_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    reporting_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    submission_date TIMESTAMP WITH TIME ZONE,
    report_data JSONB,
    file_path TEXT,
    file_hash VARCHAR(64),
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'GENERATED', 'SUBMITTED', 'ACCEPTED', 'REJECTED')),
    regulator VARCHAR(100),
    submission_reference VARCHAR(100),
    created_by VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    approval_timestamp TIMESTAMP WITH TIME ZONE
);

-- Data quality and validation results
CREATE TABLE IF NOT EXISTS reporting.data_quality_checks (
    check_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_type VARCHAR(50) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100),
    check_rule TEXT NOT NULL,
    check_result BOOLEAN NOT NULL,
    error_count INTEGER DEFAULT 0,
    error_details JSONB,
    check_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    remediation_required BOOLEAN DEFAULT FALSE,
    remediation_notes TEXT
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit.database_audit_log(audit_timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_operation ON audit.database_audit_log(table_name, operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit.database_audit_log(user_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_transaction ON audit.database_audit_log(transaction_id);

-- Transaction integrity indexes
CREATE INDEX IF NOT EXISTS idx_transaction_integrity_block ON audit.transaction_integrity_log(block_number);
CREATE INDEX IF NOT EXISTS idx_transaction_integrity_hash ON audit.transaction_integrity_log(transaction_hash);

-- User sessions indexes
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON audit.user_sessions(user_name);
CREATE INDEX IF NOT EXISTS idx_user_sessions_login_time ON audit.user_sessions(login_time);
CREATE INDEX IF NOT EXISTS idx_user_sessions_status ON audit.user_sessions(status);

-- Compliance indexes
CREATE INDEX IF NOT EXISTS idx_trade_reports_trade_id ON compliance.trade_reports(trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_reports_type_status ON compliance.trade_reports(report_type, status);
CREATE INDEX IF NOT EXISTS idx_trade_reports_timestamp ON compliance.trade_reports(reporting_timestamp);

CREATE INDEX IF NOT EXISTS idx_best_execution_trade_id ON compliance.best_execution_records(trade_id);
CREATE INDEX IF NOT EXISTS idx_best_execution_created ON compliance.best_execution_records(created_at);

CREATE INDEX IF NOT EXISTS idx_position_limits_account ON compliance.position_limits(account_id);
CREATE INDEX IF NOT EXISTS idx_position_limits_type_status ON compliance.position_limits(limit_type, status);

CREATE INDEX IF NOT EXISTS idx_compliance_breaches_type ON compliance.compliance_breaches(breach_type);
CREATE INDEX IF NOT EXISTS idx_compliance_breaches_severity ON compliance.compliance_breaches(severity);
CREATE INDEX IF NOT EXISTS idx_compliance_breaches_timestamp ON compliance.compliance_breaches(detection_timestamp);

-- Security indexes
CREATE INDEX IF NOT EXISTS idx_access_log_user_timestamp ON security.access_log(user_name, access_timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_resource ON security.access_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_access_log_session ON security.access_log(session_id);

CREATE INDEX IF NOT EXISTS idx_security_incidents_type ON security.security_incidents(incident_type);
CREATE INDEX IF NOT EXISTS idx_security_incidents_severity ON security.security_incidents(severity);
CREATE INDEX IF NOT EXISTS idx_security_incidents_timestamp ON security.security_incidents(detection_timestamp);

-- Reporting indexes
CREATE INDEX IF NOT EXISTS idx_regulatory_reports_type ON reporting.regulatory_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_regulatory_reports_period ON reporting.regulatory_reports(reporting_period_start, reporting_period_end);
CREATE INDEX IF NOT EXISTS idx_regulatory_reports_status ON reporting.regulatory_reports(status);

CREATE INDEX IF NOT EXISTS idx_data_quality_table ON reporting.data_quality_checks(table_name);
CREATE INDEX IF NOT EXISTS idx_data_quality_timestamp ON reporting.data_quality_checks(check_timestamp);

-- =============================================
-- AUDIT TRIGGER FUNCTIONS
-- =============================================

-- Generic audit trigger function for all tables
CREATE OR REPLACE FUNCTION audit.audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    audit_row audit.database_audit_log;
    include_columns TEXT[];
    exclude_columns TEXT[] = ARRAY[]::TEXT[];
    new_record JSONB;
    old_record JSONB;
    changed_fields TEXT[] = ARRAY[]::TEXT[];
    column_name TEXT;
BEGIN
    -- Skip audit logging for audit tables themselves
    IF TG_TABLE_SCHEMA = 'audit' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    audit_row = ROW(
        uuid_generate_v4(),                    -- audit_id
        TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, -- table_name
        TG_OP,                                 -- operation
        NULL,                                  -- old_values (set below)
        NULL,                                  -- new_values (set below)
        NULL,                                  -- changed_fields (set below)
        session_user,                          -- user_name
        NULL,                                  -- session_id (set from context)
        current_setting('application_name', true), -- application_name
        inet_client_addr(),                    -- client_ip
        CURRENT_TIMESTAMP,                     -- audit_timestamp
        txid_current(),                        -- transaction_id
        NULL,                                  -- row_id (set below)
        NULL                                   -- correlation_id
    );

    -- Set row_id based on operation
    IF TG_OP = 'DELETE' THEN
        old_record = to_jsonb(OLD);
        audit_row.old_values = old_record;
        -- Try to get primary key value
        BEGIN
            audit_row.row_id = (old_record->>(TG_TABLE_NAME || '_id'))::UUID;
        EXCEPTION WHEN OTHERS THEN
            -- Fallback to any id-like column
            FOR column_name IN
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = TG_TABLE_SCHEMA
                AND table_name = TG_TABLE_NAME
                AND column_name LIKE '%_id'
                LIMIT 1
            LOOP
                audit_row.row_id = (old_record->>column_name)::UUID;
                EXIT;
            END LOOP;
        END;
    ELSIF TG_OP = 'INSERT' THEN
        new_record = to_jsonb(NEW);
        audit_row.new_values = new_record;
        -- Try to get primary key value
        BEGIN
            audit_row.row_id = (new_record->>(TG_TABLE_NAME || '_id'))::UUID;
        EXCEPTION WHEN OTHERS THEN
            -- Fallback to any id-like column
            FOR column_name IN
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = TG_TABLE_SCHEMA
                AND table_name = TG_TABLE_NAME
                AND column_name LIKE '%_id'
                LIMIT 1
            LOOP
                audit_row.row_id = (new_record->>column_name)::UUID;
                EXIT;
            END LOOP;
        END;
    ELSIF TG_OP = 'UPDATE' THEN
        old_record = to_jsonb(OLD);
        new_record = to_jsonb(NEW);
        audit_row.old_values = old_record;
        audit_row.new_values = new_record;

        -- Identify changed fields
        FOR column_name IN
            SELECT key FROM jsonb_object_keys(new_record) AS key
            WHERE (old_record->>key) IS DISTINCT FROM (new_record->>key)
        LOOP
            changed_fields = array_append(changed_fields, column_name);
        END LOOP;
        audit_row.changed_fields = changed_fields;

        -- Get row ID
        BEGIN
            audit_row.row_id = (new_record->>(TG_TABLE_NAME || '_id'))::UUID;
        EXCEPTION WHEN OTHERS THEN
            -- Fallback to any id-like column
            FOR column_name IN
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = TG_TABLE_SCHEMA
                AND table_name = TG_TABLE_NAME
                AND column_name LIKE '%_id'
                LIMIT 1
            LOOP
                audit_row.row_id = (new_record->>column_name)::UUID;
                EXIT;
            END LOOP;
        END;
    END IF;

    INSERT INTO audit.database_audit_log VALUES (audit_row.*);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function to create blockchain-style integrity hash
CREATE OR REPLACE FUNCTION audit.create_integrity_hash(transaction_data JSONB, previous_hash TEXT DEFAULT NULL)
RETURNS TEXT AS $$
DECLARE
    hash_input TEXT;
    result_hash TEXT;
BEGIN
    -- Create hash input from transaction data and previous hash
    hash_input = COALESCE(previous_hash, '') || transaction_data::TEXT || extract(epoch from now())::TEXT;

    -- Generate SHA-256 hash
    result_hash = encode(digest(hash_input, 'sha256'), 'hex');

    RETURN result_hash;
END;
$$ LANGUAGE plpgsql;

-- Function to add transaction to integrity log
CREATE OR REPLACE FUNCTION audit.add_to_integrity_log(transaction_data JSONB)
RETURNS UUID AS $$
DECLARE
    log_id UUID;
    previous_hash TEXT;
    new_hash TEXT;
    block_num BIGINT;
BEGIN
    -- Get the latest block number and hash
    SELECT COALESCE(MAX(block_number), 0) + 1,
           (SELECT transaction_hash FROM audit.transaction_integrity_log
            ORDER BY block_number DESC LIMIT 1)
    INTO block_num, previous_hash;

    -- Generate new hash
    new_hash = audit.create_integrity_hash(transaction_data, previous_hash);

    -- Insert new record
    INSERT INTO audit.transaction_integrity_log (
        transaction_hash, previous_hash, block_number, transaction_data
    ) VALUES (
        new_hash, previous_hash, block_num, transaction_data
    ) RETURNING log_id INTO log_id;

    RETURN log_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- APPLY AUDIT TRIGGERS TO EXISTING TABLES
-- =============================================

-- Trading tables
DROP TRIGGER IF EXISTS audit_trigger ON trading.accounts;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON trading.accounts
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

DROP TRIGGER IF EXISTS audit_trigger ON trading.positions;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON trading.positions
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

DROP TRIGGER IF EXISTS audit_trigger ON trading.trades;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON trading.trades
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

DROP TRIGGER IF EXISTS audit_trigger ON trading.portfolio_summary;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON trading.portfolio_summary
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

DROP TRIGGER IF EXISTS audit_trigger ON trading.risk_events;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON trading.risk_events
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

-- Compliance tables
DROP TRIGGER IF EXISTS audit_trigger ON compliance.trade_reports;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON compliance.trade_reports
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

DROP TRIGGER IF EXISTS audit_trigger ON compliance.position_limits;
CREATE TRIGGER audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON compliance.position_limits
    FOR EACH ROW EXECUTE FUNCTION audit.audit_trigger_function();

-- =============================================
-- MATERIALIZED VIEWS FOR REPORTING
-- =============================================

-- Daily trading summary for regulatory reporting
CREATE MATERIALIZED VIEW IF NOT EXISTS reporting.daily_trading_summary AS
SELECT
    DATE(t.execution_time) as trading_date,
    t.account_id,
    a.account_name,
    t.symbol,
    t.instrument_type,
    COUNT(*) as trade_count,
    SUM(CASE WHEN t.action IN ('BUY', 'BUY_TO_COVER') THEN t.quantity ELSE 0 END) as total_buy_quantity,
    SUM(CASE WHEN t.action IN ('SELL', 'SELL_SHORT') THEN t.quantity ELSE 0 END) as total_sell_quantity,
    SUM(t.value) as total_value,
    SUM(t.commission + t.fees) as total_costs,
    SUM(t.realized_pnl) as total_realized_pnl,
    AVG(t.price) as avg_price,
    MIN(t.execution_time) as first_trade_time,
    MAX(t.execution_time) as last_trade_time
FROM trading.trades t
JOIN trading.accounts a ON t.account_id = a.account_id
GROUP BY DATE(t.execution_time), t.account_id, a.account_name, t.symbol, t.instrument_type;

-- Create unique index for materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_trading_summary_unique
ON reporting.daily_trading_summary(trading_date, account_id, symbol, instrument_type);

-- Risk metrics summary
CREATE MATERIALIZED VIEW IF NOT EXISTS reporting.risk_metrics_summary AS
SELECT
    DATE(timestamp) as risk_date,
    account_id,
    COUNT(*) as snapshot_count,
    AVG((risk_metrics->>'var_95')::DECIMAL) as avg_var_95,
    MAX((risk_metrics->>'var_95')::DECIMAL) as max_var_95,
    AVG((risk_metrics->>'volatility')::DECIMAL) as avg_volatility,
    MAX((risk_metrics->>'max_drawdown')::DECIMAL) as max_drawdown,
    AVG((risk_metrics->>'sharpe_ratio')::DECIMAL) as avg_sharpe_ratio
FROM trading.portfolio_summary
WHERE risk_metrics IS NOT NULL
GROUP BY DATE(timestamp), account_id;

-- Create unique index for risk metrics view
CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_metrics_summary_unique
ON reporting.risk_metrics_summary(risk_date, account_id);

-- =============================================
-- DATA RETENTION AND ARCHIVAL PROCEDURES
-- =============================================

-- Function to archive old audit data
CREATE OR REPLACE FUNCTION audit.archive_old_data(retention_months INTEGER DEFAULT 84) -- 7 years
RETURNS TABLE(archived_count BIGINT, archived_tables TEXT[]) AS $$
DECLARE
    cutoff_date TIMESTAMP WITH TIME ZONE;
    table_name TEXT;
    archived_tables TEXT[] = ARRAY[]::TEXT[];
    total_archived BIGINT = 0;
    table_archived BIGINT;
BEGIN
    cutoff_date = CURRENT_TIMESTAMP - (retention_months || ' months')::INTERVAL;

    -- Archive old audit logs
    FOR table_name IN
        SELECT schemaname || '.' || tablename
        FROM pg_tables
        WHERE schemaname = 'audit'
        AND tablename LIKE '%_archive'
    LOOP
        EXECUTE format('
            INSERT INTO %s_archive
            SELECT * FROM %s
            WHERE audit_timestamp < $1
        ', table_name, table_name) USING cutoff_date;

        GET DIAGNOSTICS table_archived = ROW_COUNT;

        IF table_archived > 0 THEN
            EXECUTE format('DELETE FROM %s WHERE audit_timestamp < $1', table_name) USING cutoff_date;
            archived_tables = array_append(archived_tables, table_name);
            total_archived = total_archived + table_archived;
        END IF;
    END LOOP;

    RETURN QUERY SELECT total_archived, archived_tables;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- COMPLIANCE MONITORING FUNCTIONS
-- =============================================

-- Function to check position limits
CREATE OR REPLACE FUNCTION compliance.check_position_limits(check_account_id UUID DEFAULT NULL)
RETURNS TABLE(
    violation_type TEXT,
    account_id UUID,
    current_value DECIMAL,
    limit_value DECIMAL,
    breach_percentage DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pl.limit_type::TEXT as violation_type,
        p.account_id,
        CASE
            WHEN pl.limit_type = 'POSITION_SIZE' THEN ABS(p.quantity * p.current_price)
            WHEN pl.limit_type = 'CONCENTRATION' THEN
                ABS(p.quantity * p.current_price) / NULLIF(ps.total_value, 0) * 100
            ELSE 0
        END as current_value,
        pl.limit_value,
        CASE
            WHEN pl.limit_value > 0 THEN
                (CASE
                    WHEN pl.limit_type = 'POSITION_SIZE' THEN ABS(p.quantity * p.current_price)
                    WHEN pl.limit_type = 'CONCENTRATION' THEN
                        ABS(p.quantity * p.current_price) / NULLIF(ps.total_value, 0) * 100
                    ELSE 0
                END) / pl.limit_value * 100
            ELSE 0
        END as breach_percentage
    FROM trading.positions p
    JOIN compliance.position_limits pl ON p.account_id = pl.account_id
    JOIN trading.portfolio_summary ps ON p.account_id = ps.account_id
    WHERE p.status = 'OPEN'
    AND pl.status = 'ACTIVE'
    AND (check_account_id IS NULL OR p.account_id = check_account_id)
    AND (
        (pl.limit_type = 'POSITION_SIZE' AND ABS(p.quantity * p.current_price) > pl.limit_value)
        OR (pl.limit_type = 'CONCENTRATION' AND
            ABS(p.quantity * p.current_price) / NULLIF(ps.total_value, 0) * 100 > pl.limit_value)
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- AUTOMATED COMPLIANCE REPORTING
-- =============================================

-- Function to generate trade report for regulatory submission
CREATE OR REPLACE FUNCTION compliance.generate_trade_report(
    report_type_param VARCHAR(50),
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE
) RETURNS JSONB AS $$
DECLARE
    report_data JSONB;
BEGIN
    SELECT jsonb_build_object(
        'report_metadata', jsonb_build_object(
            'report_type', report_type_param,
            'period_start', start_date,
            'period_end', end_date,
            'generation_timestamp', CURRENT_TIMESTAMP,
            'record_count', COUNT(*)
        ),
        'trades', jsonb_agg(
            jsonb_build_object(
                'trade_id', t.trade_id,
                'execution_time', t.execution_time,
                'symbol', t.symbol,
                'instrument_type', t.instrument_type,
                'action', t.action,
                'quantity', t.quantity,
                'price', t.price,
                'value', t.value,
                'commission', t.commission,
                'fees', t.fees,
                'exchange', t.exchange,
                'currency', t.currency,
                'account_name', a.account_name
            )
        )
    )
    INTO report_data
    FROM trading.trades t
    JOIN trading.accounts a ON t.account_id = a.account_id
    WHERE t.execution_time BETWEEN start_date AND end_date;

    -- Insert report record
    INSERT INTO reporting.regulatory_reports (
        report_type, reporting_period_start, reporting_period_end,
        report_data, created_by, status
    ) VALUES (
        report_type_param, start_date, end_date,
        report_data, session_user, 'GENERATED'
    );

    RETURN report_data;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- REFRESH MATERIALIZED VIEWS FUNCTION
-- =============================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION reporting.refresh_all_views()
RETURNS TEXT AS $$
DECLARE
    view_name TEXT;
    result TEXT = '';
BEGIN
    FOR view_name IN
        SELECT schemaname || '.' || matviewname
        FROM pg_matviews
        WHERE schemaname IN ('reporting', 'compliance')
    LOOP
        EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || view_name;
        result = result || 'Refreshed: ' || view_name || E'\n';
    END LOOP;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- GRANT PERMISSIONS
-- =============================================

-- Grant permissions to trader user
GRANT USAGE ON SCHEMA audit, compliance, security, reporting TO trader;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit TO trader;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA compliance TO trader;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA security TO trader;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA reporting TO trader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit TO trader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA compliance TO trader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA security TO trader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA reporting TO trader;

-- Grant execute permissions on functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA audit TO trader;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA compliance TO trader;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA security TO trader;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA reporting TO trader;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON SEQUENCES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT EXECUTE ON FUNCTIONS TO trader;

ALTER DEFAULT PRIVILEGES IN SCHEMA compliance GRANT ALL ON TABLES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA compliance GRANT ALL ON SEQUENCES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA compliance GRANT EXECUTE ON FUNCTIONS TO trader;

ALTER DEFAULT PRIVILEGES IN SCHEMA security GRANT ALL ON TABLES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA security GRANT ALL ON SEQUENCES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA security GRANT EXECUTE ON FUNCTIONS TO trader;

ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT ALL ON TABLES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT ALL ON SEQUENCES TO trader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT EXECUTE ON FUNCTIONS TO trader;

-- =============================================
-- INITIAL DATA AND TESTING
-- =============================================

-- Insert sample position limits
INSERT INTO compliance.position_limits (
    account_id, limit_type, limit_value, warning_threshold, created_by, approved_by
)
SELECT
    account_id,
    'POSITION_SIZE',
    10000.00,
    8000.00,
    'system',
    'compliance_officer'
FROM trading.accounts
WHERE NOT EXISTS (
    SELECT 1 FROM compliance.position_limits
    WHERE account_id = trading.accounts.account_id
    AND limit_type = 'POSITION_SIZE'
);

-- Create initial integrity hash
SELECT audit.add_to_integrity_log(
    jsonb_build_object(
        'event', 'system_initialization',
        'timestamp', CURRENT_TIMESTAMP,
        'description', 'Initial audit trail setup completed'
    )
);

-- Analyze all new tables for optimal query performance
ANALYZE audit.database_audit_log;
ANALYZE audit.transaction_integrity_log;
ANALYZE audit.user_sessions;
ANALYZE compliance.trade_reports;
ANALYZE compliance.best_execution_records;
ANALYZE compliance.position_limits;
ANALYZE compliance.compliance_breaches;
ANALYZE security.access_log;
ANALYZE security.encryption_keys;
ANALYZE security.security_incidents;
ANALYZE reporting.regulatory_reports;
ANALYZE reporting.data_quality_checks;

-- Refresh materialized views
SELECT reporting.refresh_all_views();

-- Success message
SELECT 'Production-grade audit trails and compliance framework setup completed!' as message;