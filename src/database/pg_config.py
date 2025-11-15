"""
PostgreSQL Database Configuration and Connection Management
Optimized for quantitative trading applications with connection pooling
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncContextManager
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

try:
    import asyncpg
    import psycopg2
    from psycopg2 import pool
    import json
    import hashlib
    from datetime import datetime, timezone
except ImportError:
    print("PostgreSQL dependencies not installed. Run: pip install asyncpg psycopg2-binary")
    raise

logger = logging.getLogger(__name__)

def _parse_db_url() -> Dict[str, Any]:
    """Parse DATABASE_URL into components"""
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        logger.warning("DATABASE_URL not found in environment variables")
        return {}

    logger.info(f"Parsing DATABASE_URL: {database_url[:50]}...")  # Log first 50 chars
    try:
        # Handle both postgresql:// and postgresql+asyncpg:// URLs
        if database_url.startswith('postgresql+asyncpg://'):
            url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        else:
            url = database_url

        # Parse URL format: postgresql://username:password@host:port/database?params
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)

        # Extract query parameters (like sslmode)
        query_params = parse_qs(parsed.query)

        return {
            'username': parsed.username or '',
            'password': parsed.password or '',
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'trading_db',
            'query_params': query_params,
            'original_url': database_url  # Store original URL with all parameters
        }
    except Exception as e:
        logger.warning(f"Failed to parse DATABASE_URL: {e}")
        return {}

@dataclass
class DatabaseConfig:
    """Database configuration with environment variable support"""
    # Parse DATABASE_URL if available, otherwise use individual env vars
    host: str = field(default_factory=lambda: _parse_db_url().get('host', os.getenv('POSTGRES_HOST', 'localhost')))
    port: int = field(default_factory=lambda: _parse_db_url().get('port', int(os.getenv('POSTGRES_PORT', '5432'))))
    database: str = field(default_factory=lambda: _parse_db_url().get('database', os.getenv('POSTGRES_DB', 'trading_db')))
    username: str = field(default_factory=lambda: _parse_db_url().get('username', os.getenv('POSTGRES_USER', 'trader')))
    password: str = field(default_factory=lambda: _parse_db_url().get('password', os.getenv('POSTGRES_PASSWORD', 'trading_secure_password_2024')))

    # Connection pool settings
    min_connections: int = field(default_factory=lambda: int(os.getenv('POSTGRES_MIN_CONN', '5')))
    max_connections: int = field(default_factory=lambda: int(os.getenv('POSTGRES_MAX_CONN', '25')))

    # SSL settings for production
    ssl_mode: str = field(default_factory=lambda: os.getenv('POSTGRES_SSL_MODE', 'prefer'))
    ssl_cert: Optional[str] = field(default_factory=lambda: os.getenv('POSTGRES_SSL_CERT'))
    ssl_key: Optional[str] = field(default_factory=lambda: os.getenv('POSTGRES_SSL_KEY'))
    ssl_ca: Optional[str] = field(default_factory=lambda: os.getenv('POSTGRES_SSL_CA'))

    # Query optimization settings
    command_timeout: int = field(default_factory=lambda: int(os.getenv('POSTGRES_TIMEOUT', '30')))
    statement_cache_size: int = field(default_factory=lambda: int(os.getenv('POSTGRES_CACHE_SIZE', '1024')))

    # Audit and compliance settings
    enable_audit_logging: bool = field(default_factory=lambda: os.getenv('ENABLE_AUDIT_LOGGING', 'true').lower() == 'true')
    audit_user_tracking: bool = field(default_factory=lambda: os.getenv('AUDIT_USER_TRACKING', 'true').lower() == 'true')
    enable_query_logging: bool = field(default_factory=lambda: os.getenv('ENABLE_QUERY_LOGGING', 'false').lower() == 'true')

    # Security settings
    session_timeout_minutes: int = field(default_factory=lambda: int(os.getenv('SESSION_TIMEOUT_MINUTES', '30')))
    max_failed_logins: int = field(default_factory=lambda: int(os.getenv('MAX_FAILED_LOGINS', '5')))
    require_mfa: bool = field(default_factory=lambda: os.getenv('REQUIRE_MFA', 'false').lower() == 'true')

    @property
    def connection_string(self) -> str:
        """Generate connection string for asyncpg with SSL parameters"""
        # Check if we have the original DATABASE_URL with parameters
        parsed_data = _parse_db_url()
        if parsed_data.get('original_url'):
            # Use the original URL if it exists (preserves SSL and other params)
            original_url = parsed_data['original_url']
            logger.info(f"Using original DATABASE_URL (user: {parsed_data.get('username', 'N/A')})")
            return original_url
        # Otherwise, build connection string and add SSL mode
        logger.info(f"Building connection string from components (user: {self.username})")
        base_url = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        if self.ssl_mode and self.ssl_mode != 'disable':
            return f"{base_url}?sslmode={self.ssl_mode}"
        return base_url

    @property
    def psycopg2_dsn(self) -> str:
        """Generate DSN for psycopg2"""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.username} password={self.password}"

class PostgreSQLManager:
    """Async PostgreSQL connection manager with pooling and audit trails"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None
        self._sync_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self._is_initialized = False
        self._session_registry = {}  # Track active sessions
        self._audit_context = {}  # Context for audit logging

    async def initialize(self):
        """Initialize async connection pool"""
        if self._is_initialized:
            return

        try:
            # SSL configuration
            ssl_context = None
            if self.config.ssl_mode != 'disable':
                ssl_context = self._create_ssl_context()

            # Create async connection pool with audit settings
            self._pool = await asyncpg.create_pool(
                dsn=self.config.connection_string,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=self.config.command_timeout,
                ssl=ssl_context,
                # Performance optimizations
                statement_cache_size=self.config.statement_cache_size,
                max_cached_statement_lifetime=300,  # 5 minutes
                max_inactive_connection_lifetime=1800,  # 30 minutes
                # Audit and compliance settings
                setup=self._setup_connection_audit if self.config.enable_audit_logging else None
            )

            # Create sync connection pool for Streamlit compatibility
            self._sync_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                dsn=self.config.psycopg2_dsn
            )

            self._is_initialized = True
            logger.info(f"PostgreSQL connection pools initialized (async: {self.config.min_connections}-{self.config.max_connections})")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection: {e}")
            raise

    def _create_ssl_context(self):
        """Create SSL context if SSL certificates are provided"""
        if self.config.ssl_cert and self.config.ssl_key:
            import ssl
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            if self.config.ssl_ca:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_REQUIRED
                context.load_verify_locations(self.config.ssl_ca)
            context.load_cert_chain(self.config.ssl_cert, self.config.ssl_key)
            return context
        return None

    async def _setup_connection_audit(self, connection):
        """Setup audit logging for each connection"""
        if self.config.enable_audit_logging:
            # Set application name for audit trails
            await connection.execute(
                "SET application_name = 'trading_dashboard'"
            )
            # Enable query logging if configured
            if self.config.enable_query_logging:
                await connection.execute(
                    "SET log_statement = 'all'"
                )
            # Set session timeout
            await connection.execute(
                f"SET statement_timeout = '{self.config.session_timeout_minutes * 60}s'"
            )

    @asynccontextmanager
    async def get_connection(self) -> AsyncContextManager[asyncpg.Connection]:
        """Get async database connection from pool"""
        if not self._is_initialized:
            await self.initialize()

        async with self._pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise

    def get_sync_connection(self):
        """Get sync database connection for Streamlit compatibility"""
        if not self._sync_pool:
            # Initialize sync pool if needed
            self._sync_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                dsn=self.config.psycopg2_dsn
            )

        return self._sync_pool.getconn()

    def return_sync_connection(self, connection):
        """Return sync connection to pool"""
        if self._sync_pool:
            self._sync_pool.putconn(connection)

    async def execute_query(self, query: str, params: tuple = None, audit_context: Dict = None) -> List[Dict]:
        """Execute query and return results as list of dictionaries with audit logging"""
        async with self.get_connection() as conn:
            try:
                # Log query execution for audit if enabled
                if self.config.enable_audit_logging and audit_context:
                    await self._log_query_audit(conn, query, params, 'SELECT', audit_context)

                if params:
                    result = await conn.fetch(query, *params)
                else:
                    result = await conn.fetch(query)

                return [dict(row) for row in result]
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query[:200]}...")
                # Log failed query for security monitoring
                if self.config.enable_audit_logging:
                    await self._log_security_event(conn, 'QUERY_FAILURE', str(e), audit_context)
                raise

    async def execute_command(self, query: str, params: tuple = None, audit_context: Dict = None) -> str:
        """Execute command (INSERT/UPDATE/DELETE) and return status with audit logging"""
        async with self.get_connection() as conn:
            try:
                # Determine operation type for audit
                operation = query.strip().upper().split()[0]

                # Log command execution for audit if enabled
                if self.config.enable_audit_logging and audit_context and operation in ['INSERT', 'UPDATE', 'DELETE']:
                    await self._log_query_audit(conn, query, params, operation, audit_context)

                if params:
                    result = await conn.execute(query, *params)
                else:
                    result = await conn.execute(query)
                return result
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                logger.error(f"Query: {query[:200]}...")
                # Log failed command for security monitoring
                if self.config.enable_audit_logging:
                    await self._log_security_event(conn, 'COMMAND_FAILURE', str(e), audit_context)
                raise

    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute query with multiple parameter sets (batch insert/update)"""
        async with self.get_connection() as conn:
            try:
                await conn.executemany(query, params_list)
            except Exception as e:
                logger.error(f"Batch execution failed: {e}")
                logger.error(f"Query: {query[:200]}...")
                raise

    async def execute_transaction(self, queries: List[tuple]) -> None:
        """Execute multiple queries in a transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                try:
                    for query, params in queries:
                        if params:
                            await conn.execute(query, *params)
                        else:
                            await conn.execute(query)
                except Exception as e:
                    logger.error(f"Transaction failed: {e}")
                    raise

    def execute_sync_query(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute synchronous query for Streamlit compatibility"""
        conn = self.get_sync_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    return cursor.fetchall()
                return []
        except Exception as e:
            logger.error(f"Sync query execution failed: {e}")
            raise
        finally:
            self.return_sync_connection(conn)

    def execute_sync_command(self, query: str, params: tuple = None) -> None:
        """Execute synchronous command for Streamlit compatibility"""
        conn = self.get_sync_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"Sync command execution failed: {e}")
            conn.rollback()
            raise
        finally:
            self.return_sync_connection(conn)

    async def test_connection(self) -> bool:
        """Test database connection and return status"""
        try:
            result = await self.execute_query("SELECT 1 as test")
            return result[0]['test'] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def get_table_info(self, schema: str = 'trading') -> Dict[str, List[Dict]]:
        """Get information about tables and columns in schema"""
        query = """
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = $1
        ORDER BY table_name, ordinal_position
        """

        result = await self.execute_query(query, (schema,))

        # Group by table
        tables = {}
        for row in result:
            table_name = row['table_name']
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append(row)

        return tables

    async def close(self):
        """Close all connections and cleanup"""
        if self._pool:
            await self._pool.close()
            logger.info("Async connection pool closed")

        if self._sync_pool:
            self._sync_pool.closeall()
            logger.info("Sync connection pool closed")

        self._is_initialized = False

class DatabaseInitializer:
    """Initialize database with schema and sample data"""

    def __init__(self, db_manager: PostgreSQLManager):
        self.db_manager = db_manager
        self.schema_path = Path(__file__).parent / 'schema.sql'

    async def create_database_if_not_exists(self):
        """Create database if it doesn't exist"""
        # Connect to default database to create trading database
        temp_config = DatabaseConfig()
        temp_config.database = 'postgres'  # Default database
        temp_manager = PostgreSQLManager(temp_config)

        try:
            await temp_manager.initialize()

            # Check if database exists
            check_query = "SELECT 1 FROM pg_database WHERE datname = $1"
            result = await temp_manager.execute_query(check_query, (self.db_manager.config.database,))

            if not result:
                # Create database
                create_query = f"CREATE DATABASE {self.db_manager.config.database}"
                await temp_manager.execute_command(create_query)
                logger.info(f"Database {self.db_manager.config.database} created")

        finally:
            await temp_manager.close()

    async def initialize_schema(self):
        """Initialize database schema from SQL file"""
        if not self.schema_path.exists():
            logger.error(f"Schema file not found: {self.schema_path}")
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        with open(self.schema_path, 'r') as f:
            schema_sql = f.read()

        # Split SQL commands (basic split on semicolon)
        commands = [cmd.strip() for cmd in schema_sql.split(';') if cmd.strip()]

        for command in commands:
            if command:
                try:
                    await self.db_manager.execute_command(command)
                except Exception as e:
                    logger.warning(f"Schema command failed (may already exist): {e}")
                    continue

        logger.info("Database schema initialized successfully")

    async def create_sample_account(self) -> str:
        """Create sample trading account and return account ID"""
        query = """
        INSERT INTO trading.accounts (account_name, account_type, initial_capital)
        VALUES ($1, $2, $3)
        RETURNING account_id
        """

        result = await self.db_manager.execute_query(
            query,
            ("Demo Trading Account", "PAPER", 100000.00)
        )

        account_id = result[0]['account_id']
        logger.info(f"Sample account created with ID: {account_id}")
        return account_id

    async def _log_query_audit(self, conn, query: str, params: tuple, operation: str, audit_context: Dict):
        """Log query execution to audit trail"""
        try:
            audit_data = {
                'query': query[:500],  # Truncate long queries
                'operation': operation,
                'user_name': audit_context.get('user_name', 'system'),
                'session_id': audit_context.get('session_id'),
                'client_ip': audit_context.get('client_ip'),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'params_hash': hashlib.sha256(str(params).encode()).hexdigest() if params else None
            }

            # Insert into audit log (separate transaction to avoid rollback)
            await conn.execute(
                """
                INSERT INTO audit.database_audit_log
                (table_name, operation, new_values, user_name, session_id, client_ip)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                'query_execution', operation, json.dumps(audit_data),
                audit_context.get('user_name', 'system'),
                audit_context.get('session_id'),
                audit_context.get('client_ip')
            )
        except Exception as e:
            logger.warning(f"Failed to log audit entry: {e}")

    async def _log_security_event(self, conn, event_type: str, description: str, audit_context: Dict = None):
        """Log security events to security incidents table"""
        try:
            await conn.execute(
                """
                INSERT INTO security.security_incidents
                (incident_type, severity, description, source_ip, detection_timestamp)
                VALUES ($1, $2, $3, $4, $5)
                """,
                event_type, 'MEDIUM', description,
                audit_context.get('client_ip') if audit_context else None,
                datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.warning(f"Failed to log security event: {e}")

    async def create_user_session(self, user_name: str, client_ip: str, user_agent: str, mfa_verified: bool = False) -> str:
        """Create new user session and return session ID"""
        session_id = hashlib.uuid4().hex

        try:
            await self.execute_command(
                """
                INSERT INTO audit.user_sessions
                (session_id, user_name, client_ip, user_agent, mfa_verified)
                VALUES ($1, $2, $3, $4, $5)
                """,
                (session_id, user_name, client_ip, user_agent, mfa_verified)
            )

            # Store session in registry
            self._session_registry[session_id] = {
                'user_name': user_name,
                'client_ip': client_ip,
                'created_at': datetime.now(timezone.utc),
                'last_activity': datetime.now(timezone.utc)
            }

            logger.info(f"User session created: {user_name} from {client_ip}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create user session: {e}")
            raise

    async def validate_session(self, session_id: str) -> Dict:
        """Validate user session and return session info"""
        try:
            result = await self.execute_query(
                """
                SELECT user_name, client_ip, login_time, status, mfa_verified
                FROM audit.user_sessions
                WHERE session_id = $1 AND status = 'ACTIVE'
                AND login_time > NOW() - INTERVAL '%s minutes'
                """,
                (session_id, self.config.session_timeout_minutes)
            )

            if result:
                # Update last activity
                if session_id in self._session_registry:
                    self._session_registry[session_id]['last_activity'] = datetime.now(timezone.utc)

                return result[0]
            else:
                return None

        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return None

    async def terminate_session(self, session_id: str, reason: str = 'LOGOUT'):
        """Terminate user session"""
        try:
            await self.execute_command(
                """
                UPDATE audit.user_sessions
                SET logout_time = NOW(), status = 'TERMINATED'
                WHERE session_id = $1
                """,
                (session_id,)
            )

            # Remove from registry
            if session_id in self._session_registry:
                user_name = self._session_registry[session_id]['user_name']
                del self._session_registry[session_id]
                logger.info(f"Session terminated: {user_name} - {reason}")

        except Exception as e:
            logger.error(f"Failed to terminate session: {e}")

    async def check_compliance_limits(self, account_id: str) -> List[Dict]:
        """Check position limits and compliance violations"""
        try:
            violations = await self.execute_query(
                "SELECT * FROM compliance.check_position_limits($1)",
                (account_id,)
            )

            # Log any violations found
            if violations and self.config.enable_audit_logging:
                for violation in violations:
                    await self._log_security_event(
                        None,  # Connection not available in this context
                        'COMPLIANCE_VIOLATION',
                        f"Position limit exceeded: {violation}"
                    )

            return violations

        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return []

    async def generate_audit_report(self, start_date: str, end_date: str, report_type: str = 'DAILY') -> Dict:
        """Generate comprehensive audit report"""
        try:
            # Get audit statistics
            audit_stats = await self.execute_query(
                """
                SELECT
                    operation,
                    COUNT(*) as operation_count,
                    COUNT(DISTINCT user_name) as unique_users,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM audit.database_audit_log
                WHERE audit_timestamp BETWEEN $1 AND $2
                GROUP BY operation
                ORDER BY operation_count DESC
                """,
                (start_date, end_date)
            )

            # Get security incidents
            security_incidents = await self.execute_query(
                """
                SELECT incident_type, severity, COUNT(*) as incident_count
                FROM security.security_incidents
                WHERE detection_timestamp BETWEEN $1 AND $2
                GROUP BY incident_type, severity
                ORDER BY incident_count DESC
                """,
                (start_date, end_date)
            )

            # Get compliance violations
            compliance_violations = await self.execute_query(
                """
                SELECT breach_type, severity, COUNT(*) as violation_count
                FROM compliance.compliance_breaches
                WHERE detection_timestamp BETWEEN $1 AND $2
                GROUP BY breach_type, severity
                ORDER BY violation_count DESC
                """,
                (start_date, end_date)
            )

            report = {
                'report_type': report_type,
                'period_start': start_date,
                'period_end': end_date,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'audit_statistics': audit_stats,
                'security_incidents': security_incidents,
                'compliance_violations': compliance_violations,
                'summary': {
                    'total_operations': sum(stat['operation_count'] for stat in audit_stats),
                    'total_incidents': sum(inc['incident_count'] for inc in security_incidents),
                    'total_violations': sum(viol['violation_count'] for viol in compliance_violations)
                }
            }

            # Store report in database
            await self.execute_command(
                """
                INSERT INTO reporting.regulatory_reports
                (report_type, reporting_period_start, reporting_period_end, report_data, created_by)
                VALUES ($1, $2, $3, $4, $5)
                """,
                (report_type, start_date, end_date, json.dumps(report), 'system')
            )

            return report

        except Exception as e:
            logger.error(f"Audit report generation failed: {e}")
            raise

# Global database manager instance
_db_manager: Optional[PostgreSQLManager] = None

def get_database_manager(config: DatabaseConfig = None) -> PostgreSQLManager:
    """Get global database manager instance"""
    global _db_manager

    if _db_manager is None:
        if config is None:
            config = DatabaseConfig()
        _db_manager = PostgreSQLManager(config)

    return _db_manager

async def initialize_database(config: DatabaseConfig = None) -> PostgreSQLManager:
    """Initialize database with schema and return manager"""
    if config is None:
        config = DatabaseConfig()

    db_manager = PostgreSQLManager(config)
    initializer = DatabaseInitializer(db_manager)

    try:
        # Create database if needed
        await initializer.create_database_if_not_exists()

        # Initialize connection pool
        await db_manager.initialize()

        # Initialize schema
        await initializer.initialize_schema()

        # Test connection
        if await db_manager.test_connection():
            logger.info("Database initialization completed successfully")
            return db_manager
        else:
            raise Exception("Database connection test failed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        await db_manager.close()
        raise

# Convenience functions for Streamlit integration
def create_sync_db_connection(config: DatabaseConfig = None):
    """Create synchronous database connection for Streamlit"""
    if config is None:
        config = DatabaseConfig()

    return psycopg2.connect(config.psycopg2_dsn)

async def get_async_pool() -> asyncpg.Pool:
    """
    Compatibility helper for components that need direct access to the asyncpg pool.
    Ensures the global PostgreSQL manager is initialized and returns its pool.
    """
    manager = get_database_manager()
    await manager.initialize()
    if manager._pool is None:
        raise RuntimeError("Async PostgreSQL pool is not initialized")
    return manager._pool
