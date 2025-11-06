#!/usr/bin/env python3
"""
Apply Binance Bot Schema Migration
Run this script to create bot persistence tables in PostgreSQL
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.pg_config import get_async_pool


async def apply_schema():
    """Apply the Binance bot schema"""
    print("Applying Binance bot schema...")

    try:
        pool = await get_async_pool()

        # Read schema file
        schema_file = project_root / "src" / "database" / "binance_bots_schema.sql"
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        # Execute schema
        async with pool.acquire() as conn:
            await conn.execute(schema_sql)

        print("✓ Schema applied successfully!")

        # Verify tables were created
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'binance'
                ORDER BY table_name
            """)

            print("\nCreated tables:")
            for table in tables:
                print(f"  - binance.{table['table_name']}")

            views = await conn.fetch("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'binance'
                ORDER BY table_name
            """)

            print("\nCreated views:")
            for view in views:
                print(f"  - binance.{view['table_name']}")

        await pool.close()
        print("\n✓ Migration completed successfully!")

    except Exception as e:
        print(f"\n✗ Error applying schema: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(apply_schema())
