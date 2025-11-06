#!/usr/bin/env python3
"""
Database Connection Test Script
Tests PostgreSQL connectivity for the quantitative trading system
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from database.pg_config import DatabaseConfig, PostgreSQLManager
    from api.database import test_db_connection, get_db_info, init_db
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure to install requirements: pip install -r requirements/requirements_postgresql.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_env_config():
    """Print current environment configuration"""
    print("\n" + "="*60)
    print("DATABASE CONFIGURATION")
    print("="*60)

    config_vars = [
        'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB',
        'POSTGRES_USER', 'POSTGRES_PASSWORD', 'DATABASE_URL'
    ]

    for var in config_vars:
        value = os.getenv(var, 'Not set')
        if 'PASSWORD' in var and value != 'Not set':
            value = '*' * len(value)
        print(f"{var:<20}: {value}")

    print("\nActual Config Object:")
    config = DatabaseConfig()
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Database: {config.database}")
    print(f"Username: {config.username}")
    print(f"Password: {'*' * len(config.password) if config.password else 'Not set'}")

async def test_postgres_manager():
    """Test PostgreSQL manager directly"""
    print("\n" + "="*60)
    print("TESTING POSTGRESQL MANAGER")
    print("="*60)

    config = DatabaseConfig()
    manager = PostgreSQLManager(config)

    try:
        print("Initializing connection pool...")
        await manager.initialize()
        print("✓ Connection pool initialized")

        print("Testing connection...")
        test_result = await manager.test_connection()
        if test_result:
            print("✓ Database connection successful")
        else:
            print("✗ Database connection failed")
            return False

        print("Testing basic query...")
        result = await manager.execute_query("SELECT version(), current_database(), current_user")
        if result:
            print("✓ Query execution successful")
            print(f"  PostgreSQL version: {result[0]['version']}")
            print(f"  Database: {result[0]['current_database']}")
            print(f"  User: {result[0]['current_user']}")
        else:
            print("✗ Query execution failed")

        return True

    except Exception as e:
        print(f"✗ PostgreSQL manager test failed: {e}")
        return False
    finally:
        await manager.close()

async def test_fastapi_database():
    """Test FastAPI database integration"""
    print("\n" + "="*60)
    print("TESTING FASTAPI DATABASE INTEGRATION")
    print("="*60)

    try:
        print("Initializing FastAPI database...")
        await init_db()
        print("✓ FastAPI database initialization successful")

        print("Testing database connection...")
        db_status = await test_db_connection()
        print(f"Database status: {db_status}")

        if db_status.get('status') == 'healthy':
            print("✓ Database health check passed")
        else:
            print("✗ Database health check failed")
            return False

        print("Getting database info...")
        db_info = await get_db_info()
        if db_info and 'database_info' in db_info:
            print("✓ Database info retrieved successfully")
            if db_info['database_info']:
                info = db_info['database_info']
                print(f"  Database: {info.get('database_name', 'Unknown')}")
                print(f"  User: {info.get('user_name', 'Unknown')}")
                print(f"  Server: {info.get('server_address', 'Unknown')}:{info.get('server_port', 'Unknown')}")

        return True

    except Exception as e:
        print(f"✗ FastAPI database test failed: {e}")
        return False

async def test_database_tables():
    """Test database table creation and basic operations"""
    print("\n" + "="*60)
    print("TESTING DATABASE TABLES")
    print("="*60)

    config = DatabaseConfig()
    manager = PostgreSQLManager(config)

    try:
        await manager.initialize()

        # Check if schema exists
        schema_query = """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'trading'
        """
        schema_result = await manager.execute_query(schema_query)

        if schema_result:
            print("✓ Trading schema exists")

            # List tables in trading schema
            tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'trading'
            ORDER BY table_name
            """
            tables_result = await manager.execute_query(tables_query)

            if tables_result:
                print("✓ Tables found in trading schema:")
                for table in tables_result:
                    print(f"  - {table['table_name']}")
            else:
                print("! No tables found in trading schema")

        else:
            print("! Trading schema not found")
            print("  Creating schema and tables...")

            # Create schema
            await manager.execute_command("CREATE SCHEMA IF NOT EXISTS trading")
            print("✓ Trading schema created")

        return True

    except Exception as e:
        print(f"✗ Database tables test failed: {e}")
        return False
    finally:
        await manager.close()

def test_sync_connection():
    """Test synchronous connection for Streamlit compatibility"""
    print("\n" + "="*60)
    print("TESTING SYNC CONNECTION (STREAMLIT COMPATIBILITY)")
    print("="*60)

    try:
        import psycopg2

        config = DatabaseConfig()

        print("Testing psycopg2 connection...")
        conn = psycopg2.connect(config.psycopg2_dsn)

        with conn.cursor() as cursor:
            cursor.execute("SELECT version(), current_database()")
            result = cursor.fetchone()
            print("✓ Sync connection successful")
            print(f"  Version: {result[0]}")
            print(f"  Database: {result[1]}")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Sync connection test failed: {e}")
        return False

async def main():
    """Run all database tests"""
    print("QUANTITATIVE TRADING SYSTEM - DATABASE CONNECTION TEST")
    print("=" * 60)

    # Print configuration
    print_env_config()

    # Track test results
    test_results = []

    # Test PostgreSQL manager
    result1 = await test_postgres_manager()
    test_results.append(("PostgreSQL Manager", result1))

    # Test FastAPI database integration
    result2 = await test_fastapi_database()
    test_results.append(("FastAPI Database", result2))

    # Test database tables
    result3 = await test_database_tables()
    test_results.append(("Database Tables", result3))

    # Test sync connection
    result4 = test_sync_connection()
    test_results.append(("Sync Connection", result4))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in test_results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:<25}: {status}")
        if not passed:
            all_passed = False

    print(f"\nOverall Status: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")

    if not all_passed:
        print("\nNext Steps:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check connection credentials in environment variables")
        print("3. If using Docker: docker-compose up postgres")
        print("4. If local: sudo systemctl start postgresql")

    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)