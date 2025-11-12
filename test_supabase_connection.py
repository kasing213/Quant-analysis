#!/usr/bin/env python3
"""
Test Supabase PostgreSQL connection
Run this to diagnose connection issues
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test PostgreSQL connection with detailed diagnostics"""

    print("=" * 60)
    print("Supabase Connection Diagnostics")
    print("=" * 60)

    # Check environment variables
    database_url = os.getenv('DATABASE_URL')
    postgres_host = os.getenv('POSTGRES_HOST')
    postgres_port = os.getenv('POSTGRES_PORT')
    postgres_db = os.getenv('POSTGRES_DB')
    postgres_user = os.getenv('POSTGRES_USER')
    postgres_password = os.getenv('POSTGRES_PASSWORD')

    print("\n1. Environment Variables:")
    print(f"   DATABASE_URL: {'[OK]' if database_url else '[MISSING]'}")
    print(f"   POSTGRES_HOST: {postgres_host or '[MISSING]'}")
    print(f"   POSTGRES_PORT: {postgres_port or '[MISSING]'}")
    print(f"   POSTGRES_DB: {postgres_db or '[MISSING]'}")
    print(f"   POSTGRES_USER: {'[OK]' if postgres_user else '[MISSING]'}")
    print(f"   POSTGRES_PASSWORD: {'[OK]' if postgres_password else '[MISSING]'}")

    if not database_url:
        print("\n[ERROR] DATABASE_URL not set!")
        print("   Please set the DATABASE_URL environment variable")
        return False

    # Parse connection string
    print("\n2. Parsing Connection String:")
    from urllib.parse import urlparse
    try:
        parsed = urlparse(database_url)
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        print(f"   Database: {parsed.path.lstrip('/')}")
        print(f"   Username: {parsed.username}")
        print(f"   Password: {'*' * 8} (hidden)")
    except Exception as e:
        print(f"   [ERROR] Failed to parse: {e}")
        return False

    # Test network connectivity
    print("\n3. Testing Network Connectivity:")
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((parsed.hostname, parsed.port or 5432))
        sock.close()

        if result == 0:
            print(f"   [OK] Can reach {parsed.hostname}:{parsed.port}")
        else:
            print(f"   [ERROR] Cannot reach {parsed.hostname}:{parsed.port}")
            print(f"   Error code: {result}")
            return False
    except Exception as e:
        print(f"   [ERROR] Network test failed: {e}")
        return False

    # Test PostgreSQL connection with asyncpg
    print("\n4. Testing PostgreSQL Connection (asyncpg):")
    try:
        import asyncpg

        # Try to connect
        conn = await asyncpg.connect(database_url, timeout=10)
        print("   [OK] Successfully connected to PostgreSQL!")

        # Test query
        result = await conn.fetchval("SELECT version()")
        print(f"   PostgreSQL version: {result[:50]}...")

        # Test query
        result = await conn.fetchval("SELECT current_database()")
        print(f"   Current database: {result}")

        await conn.close()
        print("   [OK] Connection closed successfully")

        return True

    except Exception as e:
        print(f"   [ERROR] Connection failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nStarting connection test...")

    try:
        result = asyncio.run(test_connection())

        print("\n" + "=" * 60)
        if result:
            print("[SUCCESS] All tests passed! Connection is working.")
        else:
            print("[FAILED] Connection test failed. See errors above.")
        print("=" * 60)

        sys.exit(0 if result else 1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
