#!/usr/bin/env python3
"""
Apply Binance Bot Schema Migration - Direct Version
Run this script to create bot persistence tables in PostgreSQL
"""

import asyncio
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
load_dotenv(env_file)


async def apply_schema():
    """Apply the Binance bot schema"""
    print("Applying Binance bot schema...")
    print(f"Project root: {project_root}")

    # Get database connection info
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))
    db_name = os.getenv("POSTGRES_DB", "trading_db")
    db_user = os.getenv("POSTGRES_USER", "trader")
    db_password = os.getenv("POSTGRES_PASSWORD", "")

    print(f"\nConnecting to: {db_user}@{db_host}:{db_port}/{db_name}")

    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )

        print("✓ Connected to database")

        # Read schema file
        schema_file = project_root / "src" / "database" / "binance_bots_schema.sql"
        print(f"\nReading schema from: {schema_file}")

        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        # Execute schema
        print("\nExecuting schema...")
        await conn.execute(schema_sql)
        print("✓ Schema applied successfully!")

        # Verify tables were created
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'binance'
            ORDER BY table_name
        """)

        print(f"\nCreated tables ({len(tables)} total):")
        for table in tables:
            print(f"  ✓ binance.{table['table_name']}")

        # Verify views
        views = await conn.fetch("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'binance'
            ORDER BY table_name
        """)

        print(f"\nCreated views ({len(views)} total):")
        for view in views:
            print(f"  ✓ binance.{view['table_name']}")

        # Verify functions
        functions = await conn.fetch("""
            SELECT routine_name
            FROM information_schema.routines
            WHERE routine_schema = 'binance'
            ORDER BY routine_name
        """)

        print(f"\nCreated functions ({len(functions)} total):")
        for func in functions:
            print(f"  ✓ binance.{func['routine_name']}()")

        await conn.close()
        print("\n✓ Migration completed successfully!")
        return True

    except asyncpg.exceptions.InvalidCatalogNameError:
        print(f"\n✗ Error: Database '{db_name}' does not exist")
        print(f"Please create it first:")
        print(f"  CREATE DATABASE {db_name};")
        return False
    except asyncpg.exceptions.InvalidPasswordError:
        print(f"\n✗ Error: Invalid password for user '{db_user}'")
        return False
    except FileNotFoundError as e:
        print(f"\n✗ Error: Schema file not found: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Error applying schema: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(apply_schema())
    exit(0 if success else 1)
