#!/usr/bin/env python
"""Test Supabase PostgreSQL connection"""
import asyncio
import asyncpg
import sys

async def test_connection():
    """Test connection to Supabase PostgreSQL"""
    connection_params = {
        'host': 'aws-1-ap-southeast-2.pooler.supabase.com',
        'port': 5432,
        'user': 'postgres.wsqwoeqetggqkktkgoxo',
        'password': 'Kasingchan223699.',
        'database': 'postgres'
    }

    print("Testing Supabase PostgreSQL connection...")
    print(f"Host: {connection_params['host']}")
    print(f"User: {connection_params['user']}")
    print(f"Database: {connection_params['database']}")
    print("-" * 50)

    try:
        # Test connection
        conn = await asyncpg.connect(**connection_params)
        print("SUCCESS: Connection successful!")

        # Get database info
        result = await conn.fetchrow('SELECT current_database(), current_user, version()')
        print(f"\nDatabase: {result[0]}")
        print(f"Current User: {result[1]}")
        print(f"PostgreSQL Version: {result[2][:80]}")

        # List all tables in public schema
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        print(f"\nTables in 'public' schema: {len(tables)}")
        if tables:
            for table in tables:
                print(f"  - {table['table_name']}")
        else:
            print("  (No tables found - database is empty)")

        # Check if trading_db database exists
        databases = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false")
        print(f"\nAvailable databases:")
        for db in databases:
            print(f"  - {db['datname']}")

        await conn.close()
        print("\n✅ Connection test completed successfully!")
        return True

    except asyncpg.exceptions.InvalidPasswordError as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\nPossible issues:")
        print("1. Password is incorrect")
        print("2. Username format is wrong")
        print("3. Database name is incorrect")
        return False

    except Exception as e:
        print(f"\nERROR: Connection failed: {type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Network/firewall blocking connection")
        print("2. Supabase project is paused or deleted")
        print("3. Incorrect host/port")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
