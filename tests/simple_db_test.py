#!/usr/bin/env python3
"""
Simple Database Connection Test
Tests PostgreSQL connectivity without complex imports
"""

import asyncio
import os
import sys

def print_config():
    """Print database configuration"""
    print("="*60)
    print("DATABASE CONFIGURATION")
    print("="*60)

    config = {
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'POSTGRES_PORT': os.getenv('POSTGRES_PORT', '5432'),
        'POSTGRES_DB': os.getenv('POSTGRES_DB', 'trading_db'),
        'POSTGRES_USER': os.getenv('POSTGRES_USER', 'trader'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD', 'trading_secure_password_2024'),
        'DATABASE_URL': os.getenv('DATABASE_URL', 'Not set')
    }

    for key, value in config.items():
        if 'PASSWORD' in key and value != 'Not set':
            value = '*' * len(value)
        print(f"{key:<20}: {value}")

async def test_asyncpg():
    """Test asyncpg connection"""
    print("\n" + "="*60)
    print("TESTING ASYNCPG CONNECTION")
    print("="*60)

    try:
        import asyncpg

        # Connection parameters
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', '5432'))
        database = os.getenv('POSTGRES_DB', 'trading_db')
        user = os.getenv('POSTGRES_USER', 'trader')
        password = os.getenv('POSTGRES_PASSWORD', 'trading_secure_password_2024')

        print(f"Connecting to {user}@{host}:{port}/{database}")

        # Test connection
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        # Test query
        result = await conn.fetch("SELECT version(), current_database(), current_user")

        print("✓ AsyncPG connection successful")
        print(f"  Database: {result[0]['current_database']}")
        print(f"  User: {result[0]['current_user']}")
        print(f"  Version: {result[0]['version'][:50]}...")

        await conn.close()
        return True

    except Exception as e:
        print(f"✗ AsyncPG connection failed: {e}")
        return False

def test_psycopg2():
    """Test psycopg2 connection"""
    print("\n" + "="*60)
    print("TESTING PSYCOPG2 CONNECTION")
    print("="*60)

    try:
        import psycopg2

        # Connection parameters
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', '5432'))
        database = os.getenv('POSTGRES_DB', 'trading_db')
        user = os.getenv('POSTGRES_USER', 'trader')
        password = os.getenv('POSTGRES_PASSWORD', 'trading_secure_password_2024')

        print(f"Connecting to {user}@{host}:{port}/{database}")

        # Test connection
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        with conn.cursor() as cursor:
            cursor.execute("SELECT version(), current_database(), current_user")
            result = cursor.fetchone()

        print("✓ Psycopg2 connection successful")
        print(f"  Database: {result[1]}")
        print(f"  User: {result[2]}")
        print(f"  Version: {result[0][:50]}...")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Psycopg2 connection failed: {e}")
        return False

async def test_database_structure():
    """Test database structure"""
    print("\n" + "="*60)
    print("TESTING DATABASE STRUCTURE")
    print("="*60)

    try:
        import asyncpg

        # Connection parameters
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', '5432'))
        database = os.getenv('POSTGRES_DB', 'trading_db')
        user = os.getenv('POSTGRES_USER', 'trader')
        password = os.getenv('POSTGRES_PASSWORD', 'trading_secure_password_2024')

        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        # Check schemas
        schemas = await conn.fetch("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
        """)

        print("✓ Database schemas:")
        for schema in schemas:
            print(f"  - {schema['schema_name']}")

        # Check tables
        tables = await conn.fetch("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """)

        if tables:
            print("✓ Database tables:")
            current_schema = None
            for table in tables:
                if table['table_schema'] != current_schema:
                    current_schema = table['table_schema']
                    print(f"  {current_schema}:")
                print(f"    - {table['table_name']}")
        else:
            print("! No custom tables found")

        await conn.close()
        return True

    except Exception as e:
        print(f"✗ Database structure test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("QUANTITATIVE TRADING SYSTEM - SIMPLE DATABASE TEST")
    print("=" * 60)

    # Print configuration
    print_config()

    # Run tests
    tests = [
        ("AsyncPG Connection", test_asyncpg()),
        ("Psycopg2 Connection", test_psycopg2),
        ("Database Structure", test_database_structure())
    ]

    results = []
    for test_name, test_func in tests:
        if asyncio.iscoroutine(test_func):
            result = await test_func
        else:
            result = test_func()
        results.append((test_name, result))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:<25}: {status}")
        if not passed:
            all_passed = False

    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")

    if not all_passed:
        print("\nTroubleshooting:")
        print("1. Start PostgreSQL: docker-compose up postgres -d")
        print("2. Check connection: docker-compose ps")
        print("3. View logs: docker-compose logs postgres")
        print("4. Connect manually: docker-compose exec postgres psql -U trader trading_db")

    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)