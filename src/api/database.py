import os
import asyncio
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

try:
    import asyncpg
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import text, event
    from sqlalchemy.pool import NullPool
except ImportError:
    print("PostgreSQL async dependencies not installed. Run: pip install asyncpg sqlalchemy[asyncio]")
    raise

from ..database.pg_config import DatabaseConfig, PostgreSQLManager, get_database_manager

logger = logging.getLogger(__name__)

# PostgreSQL Database Configuration
# Ensure asyncpg dialect is used for async operations
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    # Convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Remove pgbouncer parameter if present (not compatible with asyncpg)
    if "?pgbouncer=" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?pgbouncer=")[0]
elif not DATABASE_URL:
    # Default for local development
    DATABASE_URL = "postgresql+asyncpg://trader:trading_secure_password_2024@localhost:5432/trading_db"

# Create async engine with connection pooling optimized for quantitative trading
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=15,  # Increased for high-frequency operations
    max_overflow=25,
    pool_recycle=3600,  # Recycle connections every hour
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Enable SQL logging in dev
    poolclass=NullPool if os.getenv("TESTING") else None,  # Use NullPool for testing
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()

# Global database manager for direct PostgreSQL operations
_pg_manager: Optional[PostgreSQLManager] = None

def get_pg_manager() -> PostgreSQLManager:
    """Get PostgreSQL manager for direct database operations"""
    global _pg_manager
    if _pg_manager is None:
        config = DatabaseConfig()
        _pg_manager = PostgreSQLManager(config)
    return _pg_manager

async def init_db():
    """Initialize database schema and connections"""
    try:
        # Initialize PostgreSQL manager
        pg_manager = get_pg_manager()
        await pg_manager.initialize()

        # Test connection
        if not await pg_manager.test_connection():
            raise Exception("PostgreSQL connection test failed")

        # Create tables using SQLAlchemy
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

async def test_db_connection() -> dict:
    """Test database connection and return status"""
    try:
        # Test async connection
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()

        # Test PostgreSQL manager connection
        pg_manager = get_pg_manager()
        pg_test = await pg_manager.test_connection()

        return {
            "sqlalchemy_async": test_value == 1,
            "postgresql_manager": pg_test,
            "status": "healthy" if (test_value == 1 and pg_test) else "unhealthy"
        }
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "sqlalchemy_async": False,
            "postgresql_manager": False,
            "status": "unhealthy",
            "error": str(e)
        }

async def get_db_info() -> dict:
    """Get database connection and performance information"""
    try:
        pg_manager = get_pg_manager()

        # Get basic database info
        info_query = """
        SELECT
            version() as postgres_version,
            current_database() as database_name,
            current_user as user_name,
            inet_server_addr() as server_address,
            inet_server_port() as server_port
        """

        db_info = await pg_manager.execute_query(info_query)

        # Get connection pool info
        pool_info = {
            "async_engine_pool_size": async_engine.pool.size(),
            "async_engine_checked_out": async_engine.pool.checkedout(),
            "async_engine_overflow": async_engine.pool.overflow(),
        }

        return {
            "database_info": db_info[0] if db_info else {},
            "connection_pool": pool_info,
            "config": {
                "database_url": DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('://')[1], "***"),
                "pool_size": async_engine.pool.size(),
                "max_overflow": async_engine.pool.overflow(),
            }
        }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {"error": str(e)}

@asynccontextmanager
async def get_pg_connection():
    """Get direct PostgreSQL connection for advanced operations"""
    pg_manager = get_pg_manager()
    async with pg_manager.get_connection() as conn:
        yield conn

async def execute_raw_query(query: str, params: tuple = None):
    """Execute raw PostgreSQL query for complex operations"""
    pg_manager = get_pg_manager()
    return await pg_manager.execute_query(query, params)

async def close_db_connections():
    """Close all database connections and pools"""
    global _pg_manager

    try:
        # Close async engine
        await async_engine.dispose()

        # Close PostgreSQL manager
        if _pg_manager:
            await _pg_manager.close()
            _pg_manager = None

        logger.info("All database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

# Event handlers for connection management
@event.listens_for(async_engine.sync_engine, "connect")
def set_postgresql_search_path(dbapi_connection, connection_record):
    """Set search path for new connections"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET search_path TO public, trading")
    finally:
        cursor.close()

@event.listens_for(async_engine.sync_engine, "connect")
def set_postgresql_timezone(dbapi_connection, connection_record):
    """Set timezone for new connections"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET timezone = 'UTC'")
    finally:
        cursor.close()

# Legacy sync support for compatibility
def get_db():
    """Legacy sync database session (deprecated, use get_async_db instead)"""
    logger.warning("Using deprecated sync database session. Migrate to async!")
    raise NotImplementedError("Sync database sessions are deprecated. Use get_async_db() instead.")