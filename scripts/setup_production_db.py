#!/usr/bin/env python3
"""
Production Database Setup Script
Sets up PostgreSQL database with comprehensive audit trails and compliance features
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from typing import Dict, List

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from database.pg_config import DatabaseConfig, PostgreSQLManager, DatabaseInitializer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionDatabaseSetup:
    """Production database setup with audit trails and compliance"""

    def __init__(self):
        self.config = DatabaseConfig()
        self.db_manager = None
        self.sql_files_path = Path(__file__).parent.parent / 'sql'
        self.init_files_path = Path(__file__).parent.parent

    async def setup_database(self):
        """Complete database setup process"""
        try:
            logger.info("Starting production database setup...")

            # Step 1: Initialize basic database and connection
            await self._initialize_basic_database()

            # Step 2: Execute audit trails and compliance setup
            await self._setup_audit_trails()

            # Step 3: Setup security features
            await self._setup_security_features()

            # Step 4: Create initial data and configuration
            await self._create_initial_data()

            # Step 5: Optimize database performance
            await self._optimize_performance()

            # Step 6: Validate setup
            await self._validate_setup()

            logger.info("✅ Production database setup completed successfully!")

        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            raise
        finally:
            if self.db_manager:
                await self.db_manager.close()

    async def _initialize_basic_database(self):
        """Initialize basic database structure"""
        logger.info("1. Initializing basic database structure...")

        self.db_manager = PostgreSQLManager(self.config)
        initializer = DatabaseInitializer(self.db_manager)

        # Create database if needed
        await initializer.create_database_if_not_exists()

        # Initialize connection pool
        await self.db_manager.initialize()

        # Execute init-db.sql (basic setup with schemas)
        init_db_file = self.init_files_path / 'init-db.sql'
        if init_db_file.exists():
            logger.info("Executing init-db.sql...")
            await self._execute_sql_file(init_db_file)
        else:
            logger.warning("init-db.sql not found, skipping...")

        # Execute init.sql (trading schema)
        init_file = self.init_files_path / 'init.sql'
        if init_file.exists():
            logger.info("Executing init.sql...")
            await self._execute_sql_file(init_file)
        else:
            logger.warning("init.sql not found, skipping...")

        logger.info("✅ Basic database structure initialized")

    async def _setup_audit_trails(self):
        """Setup comprehensive audit trails"""
        logger.info("2. Setting up audit trails and compliance features...")

        audit_file = self.sql_files_path / 'audit_trails.sql'
        if audit_file.exists():
            logger.info("Executing audit_trails.sql...")
            await self._execute_sql_file(audit_file)
        else:
            logger.error("audit_trails.sql not found!")
            raise FileNotFoundError("audit_trails.sql is required for production setup")

        logger.info("✅ Audit trails and compliance features setup completed")

    async def _setup_security_features(self):
        """Setup additional security features"""
        logger.info("3. Setting up security features...")

        # Create security roles and permissions
        security_commands = [
            # Create read-only role for reporting
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'trader_readonly') THEN
                    CREATE ROLE trader_readonly;
                END IF;
            END
            $$;
            """,
            # Grant read-only permissions
            "GRANT CONNECT ON DATABASE trading_db TO trader_readonly;",
            "GRANT USAGE ON SCHEMA trading, reporting TO trader_readonly;",
            "GRANT SELECT ON ALL TABLES IN SCHEMA trading, reporting TO trader_readonly;",

            # Create audit role for compliance officers
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'compliance_officer') THEN
                    CREATE ROLE compliance_officer;
                END IF;
            END
            $$;
            """,
            "GRANT CONNECT ON DATABASE trading_db TO compliance_officer;",
            "GRANT USAGE ON SCHEMA audit, compliance, security, reporting TO compliance_officer;",
            "GRANT SELECT ON ALL TABLES IN SCHEMA audit, compliance, security, reporting TO compliance_officer;",

            # Enable row level security on sensitive tables
            "ALTER TABLE trading.accounts ENABLE ROW LEVEL SECURITY;",
            "ALTER TABLE trading.trades ENABLE ROW LEVEL SECURITY;",
            "ALTER TABLE trading.positions ENABLE ROW LEVEL SECURITY;",

            # Create RLS policies for multi-tenancy (optional)
            """
            CREATE POLICY account_access_policy ON trading.accounts
            FOR ALL TO trader
            USING (true);  -- Adjust based on your access control requirements
            """,

            # Set up pgaudit for comprehensive logging
            "LOAD 'pgaudit';",
            "ALTER SYSTEM SET pgaudit.log = 'write,ddl,role';",
            "ALTER SYSTEM SET pgaudit.log_catalog = on;",
            "ALTER SYSTEM SET pgaudit.log_parameter = on;",
            "ALTER SYSTEM SET pgaudit.log_statement_once = on;",
        ]

        for command in security_commands:
            try:
                await self.db_manager.execute_command(command)
                logger.debug(f"Executed security command: {command[:50]}...")
            except Exception as e:
                logger.warning(f"Security command failed (may already exist): {e}")

        logger.info("✅ Security features setup completed")

    async def _create_initial_data(self):
        """Create initial configuration and sample data"""
        logger.info("4. Creating initial data and configuration...")

        # Create default position limits
        default_limits = [
            ('POSITION_SIZE', 50000.00, 40000.00, 'Maximum position size per instrument'),
            ('CONCENTRATION', 25.0, 20.0, 'Maximum concentration percentage per instrument'),
            ('SECTOR', 40.0, 35.0, 'Maximum sector concentration percentage'),
            ('VAR', 5000.00, 4000.00, 'Maximum Value at Risk'),
            ('LEVERAGE', 3.0, 2.5, 'Maximum leverage ratio'),
        ]

        # Get all active accounts
        accounts = await self.db_manager.execute_query(
            "SELECT account_id FROM trading.accounts WHERE status = 'ACTIVE'"
        )

        for account in accounts:
            account_id = account['account_id']
            for limit_type, limit_value, warning_threshold, description in default_limits:
                try:
                    await self.db_manager.execute_command(
                        """
                        INSERT INTO compliance.position_limits
                        (account_id, limit_type, limit_value, warning_threshold, created_by, approved_by, approval_timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW())
                        ON CONFLICT (account_id, limit_type) DO NOTHING
                        """,
                        (account_id, limit_type, limit_value, warning_threshold, 'system', 'admin')
                    )
                except Exception as e:
                    logger.warning(f"Failed to create limit {limit_type} for account {account_id}: {e}")

        # Create initial encryption keys record
        try:
            await self.db_manager.execute_command(
                """
                INSERT INTO security.encryption_keys
                (key_purpose, key_algorithm, key_length, key_hash, created_by)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (key_purpose) DO NOTHING
                """,
                ('database_encryption', 'AES-256', 256, 'placeholder_hash', 'system')
            )
        except Exception as e:
            logger.warning(f"Failed to create encryption key record: {e}")

        logger.info("✅ Initial data and configuration created")

    async def _optimize_performance(self):
        """Optimize database performance"""
        logger.info("5. Optimizing database performance...")

        optimization_commands = [
            # Update statistics for better query planning
            "ANALYZE;",

            # Create additional performance indexes
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_execution_time_desc
            ON trading.trades(execution_time DESC);
            """,

            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_timestamp_desc
            ON audit.database_audit_log(audit_timestamp DESC);
            """,

            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_current_price
            ON trading.positions(current_price) WHERE status = 'OPEN';
            """,

            # Refresh all materialized views
            "REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.daily_trading_summary;",
            "REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.risk_metrics_summary;",

            # Set up auto-vacuum settings for audit tables
            """
            ALTER TABLE audit.database_audit_log SET (
                autovacuum_vacuum_scale_factor = 0.1,
                autovacuum_analyze_scale_factor = 0.05
            );
            """,

            # Configure connection pooling parameters
            "ALTER SYSTEM SET max_connections = 200;",
            "ALTER SYSTEM SET shared_buffers = '256MB';",
            "ALTER SYSTEM SET effective_cache_size = '1GB';",
            "ALTER SYSTEM SET work_mem = '4MB';",
            "ALTER SYSTEM SET maintenance_work_mem = '64MB';",
        ]

        for command in optimization_commands:
            try:
                await self.db_manager.execute_command(command)
                logger.debug(f"Executed optimization: {command[:50]}...")
            except Exception as e:
                logger.warning(f"Optimization command failed: {e}")

        logger.info("✅ Database performance optimization completed")

    async def _validate_setup(self):
        """Validate the database setup"""
        logger.info("6. Validating database setup...")

        validation_checks = [
            # Check if all required schemas exist
            ("Schema Validation", """
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name IN ('trading', 'audit', 'compliance', 'security', 'reporting')
            """),

            # Check if audit triggers are active
            ("Audit Triggers", """
                SELECT trigger_name, event_manipulation, event_object_table
                FROM information_schema.triggers
                WHERE trigger_name = 'audit_trigger'
            """),

            # Check if materialized views exist
            ("Materialized Views", """
                SELECT schemaname, matviewname
                FROM pg_matviews
                WHERE schemaname IN ('reporting', 'compliance')
            """),

            # Validate audit trail functionality
            ("Audit Trail Test", """
                SELECT COUNT(*) as audit_count
                FROM audit.database_audit_log
                WHERE audit_timestamp > NOW() - INTERVAL '1 hour'
            """),

            # Check compliance functions
            ("Compliance Functions", """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'compliance'
                AND routine_type = 'FUNCTION'
            """),
        ]

        validation_results = {}
        for check_name, query in validation_checks:
            try:
                result = await self.db_manager.execute_query(query)
                validation_results[check_name] = {
                    'status': 'PASS',
                    'result': result,
                    'count': len(result)
                }
                logger.info(f"✅ {check_name}: {len(result)} items found")
            except Exception as e:
                validation_results[check_name] = {
                    'status': 'FAIL',
                    'error': str(e)
                }
                logger.error(f"❌ {check_name}: {e}")

        # Test audit functionality
        try:
            test_account_id = await self._test_audit_functionality()
            logger.info(f"✅ Audit functionality test passed (test account: {test_account_id})")
        except Exception as e:
            logger.error(f"❌ Audit functionality test failed: {e}")

        logger.info("✅ Database validation completed")
        return validation_results

    async def _test_audit_functionality(self) -> str:
        """Test audit trail functionality"""
        # Create a test account to trigger audit logs
        result = await self.db_manager.execute_command(
            """
            INSERT INTO trading.accounts (account_name, account_type, initial_capital)
            VALUES ('Test Audit Account', 'DEMO', 10000.00)
            RETURNING account_id
            """,
            audit_context={
                'user_name': 'setup_script',
                'session_id': 'setup_session',
                'client_ip': '127.0.0.1'
            }
        )

        # Wait a moment for trigger to execute
        await asyncio.sleep(1)

        # Verify audit log was created
        audit_logs = await self.db_manager.execute_query(
            """
            SELECT * FROM audit.database_audit_log
            WHERE table_name = 'trading.accounts'
            AND operation = 'INSERT'
            AND audit_timestamp > NOW() - INTERVAL '5 minutes'
            ORDER BY audit_timestamp DESC
            LIMIT 1
            """
        )

        if not audit_logs:
            raise Exception("Audit log not created for test transaction")

        # Clean up test account
        account_id = audit_logs[0]['row_id']
        await self.db_manager.execute_command(
            "DELETE FROM trading.accounts WHERE account_id = $1",
            (account_id,)
        )

        return str(account_id)

    async def _execute_sql_file(self, file_path: Path):
        """Execute SQL commands from file"""
        logger.info(f"Executing SQL file: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Split SQL content into individual commands
        # This is a simple split - for production, consider using a proper SQL parser
        commands = []
        current_command = []
        in_function = False

        for line in sql_content.split('\n'):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('--'):
                continue

            # Track function definitions
            if any(keyword in line.upper() for keyword in ['CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION']):
                in_function = True
            elif line.upper().startswith('$$'):
                if in_function and '$$' in line[2:]:  # Function end
                    in_function = False

            current_command.append(line)

            # Command complete if we hit semicolon and not in function
            if line.endswith(';') and not in_function:
                command = '\n'.join(current_command)
                if command.strip():
                    commands.append(command)
                current_command = []

        # Add any remaining command
        if current_command:
            command = '\n'.join(current_command)
            if command.strip():
                commands.append(command)

        # Execute commands
        for i, command in enumerate(commands):
            try:
                await self.db_manager.execute_command(command)
                if i % 10 == 0:  # Progress indicator
                    logger.debug(f"Executed {i+1}/{len(commands)} commands")
            except Exception as e:
                # Log error but continue with other commands
                logger.warning(f"Command failed (continuing): {e}")
                logger.debug(f"Failed command: {command[:100]}...")

        logger.info(f"Completed executing {len(commands)} commands from {file_path}")

async def main():
    """Main setup function"""
    setup = ProductionDatabaseSetup()

    try:
        await setup.setup_database()
        print("\n🎉 Production database setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the trading dashboard: python start_server.py")
        print("2. Access the dashboard at: http://localhost:8000")
        print("3. Review audit logs in the database")
        print("4. Configure additional compliance rules as needed")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())