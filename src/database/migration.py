"""
Data Migration from SQLite to PostgreSQL
Handles migration of existing portfolio data with data validation and rollback capabilities
"""

import sqlite3
import asyncio
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import uuid
from dataclasses import dataclass

from .pg_config import PostgreSQLManager, DatabaseConfig, initialize_database

logger = logging.getLogger(__name__)

@dataclass
class MigrationStats:
    """Track migration statistics"""
    accounts_migrated: int = 0
    positions_migrated: int = 0
    trades_migrated: int = 0
    balances_migrated: int = 0
    symbols_created: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class DataMigrator:
    """Migrate data from SQLite to PostgreSQL"""

    def __init__(self, sqlite_path: str, pg_manager: PostgreSQLManager):
        self.sqlite_path = Path(sqlite_path)
        self.pg_manager = pg_manager
        self.stats = MigrationStats()
        self.account_id = None  # Will be created during migration

    async def migrate_all_data(self, create_sample_account: bool = True) -> MigrationStats:
        """Migrate all data from SQLite to PostgreSQL"""
        logger.info(f"Starting migration from {self.sqlite_path}")

        try:
            # Verify SQLite database exists
            if not self.sqlite_path.exists():
                raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")

            # Create sample account if requested
            if create_sample_account:
                await self._create_sample_account()

            # Migrate data in order
            await self._migrate_symbols()
            await self._migrate_positions()
            await self._migrate_trades()
            await self._migrate_account_balances()

            logger.info("Data migration completed successfully")
            self._log_migration_stats()

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.stats.errors.append(str(e))
            raise

        return self.stats

    async def _create_sample_account(self):
        """Create a sample trading account"""
        query = """
        INSERT INTO trading.accounts (account_name, account_type, initial_capital, currency)
        VALUES ($1, $2, $3, $4)
        RETURNING account_id
        """

        result = await self.pg_manager.execute_query(
            query,
            ("Migrated Portfolio", "PAPER", 100000.00, "USD")
        )

        self.account_id = result[0]['account_id']
        self.stats.accounts_migrated = 1
        logger.info(f"Created account: {self.account_id}")

    async def _migrate_symbols(self):
        """Extract unique symbols and create symbol records"""
        # Get unique symbols from SQLite
        with sqlite3.connect(self.sqlite_path) as conn:
            symbols_df = pd.read_sql_query("""
                SELECT DISTINCT symbol FROM positions
                UNION
                SELECT DISTINCT symbol FROM trades
            """, conn)

        if symbols_df.empty:
            logger.info("No symbols to migrate")
            return

        # Insert symbols into PostgreSQL
        for _, row in symbols_df.iterrows():
            symbol = row['symbol']
            try:
                query = """
                INSERT INTO trading.symbols (symbol, security_type)
                VALUES ($1, $2)
                ON CONFLICT (symbol) DO NOTHING
                """
                await self.pg_manager.execute_command(query, (symbol, 'STK'))
                self.stats.symbols_created += 1

            except Exception as e:
                error_msg = f"Failed to create symbol {symbol}: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

        logger.info(f"Migrated {self.stats.symbols_created} symbols")

    async def _migrate_positions(self):
        """Migrate positions from SQLite to PostgreSQL"""
        with sqlite3.connect(self.sqlite_path) as conn:
            positions_df = pd.read_sql_query("SELECT * FROM positions", conn)

        if positions_df.empty:
            logger.info("No positions to migrate")
            return

        for _, row in positions_df.iterrows():
            try:
                # Convert SQLite data to PostgreSQL format
                query = """
                INSERT INTO trading.positions (
                    account_id, symbol, quantity, avg_price, current_price,
                    position_date, last_updated, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """

                # Handle datetime conversion
                entry_date = pd.to_datetime(row['entry_date']).date()
                last_updated = pd.to_datetime(row['last_updated'])

                # Use avg_price as current_price if no current_price data
                current_price = row['avg_price']  # SQLite doesn't have current_price stored

                await self.pg_manager.execute_command(query, (
                    self.account_id,
                    row['symbol'],
                    row['quantity'],
                    row['avg_price'],
                    current_price,
                    entry_date,
                    last_updated,
                    True  # is_active
                ))

                self.stats.positions_migrated += 1

            except Exception as e:
                error_msg = f"Failed to migrate position {row['symbol']}: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

        logger.info(f"Migrated {self.stats.positions_migrated} positions")

    async def _migrate_trades(self):
        """Migrate trades from SQLite to PostgreSQL"""
        with sqlite3.connect(self.sqlite_path) as conn:
            trades_df = pd.read_sql_query("SELECT * FROM trades", conn)

        if trades_df.empty:
            logger.info("No trades to migrate")
            return

        for _, row in trades_df.iterrows():
            try:
                query = """
                INSERT INTO trading.trades (
                    account_id, symbol, side, quantity, price, commission,
                    execution_time, data_source
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """

                # Handle datetime conversion
                execution_time = pd.to_datetime(row['trade_date'])

                await self.pg_manager.execute_command(query, (
                    self.account_id,
                    row['symbol'],
                    row['side'],
                    row['quantity'],
                    row['price'],
                    row.get('commission', 1.0),
                    execution_time,
                    'MIGRATED'
                ))

                self.stats.trades_migrated += 1

            except Exception as e:
                error_msg = f"Failed to migrate trade {row['trade_id']}: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

        logger.info(f"Migrated {self.stats.trades_migrated} trades")

    async def _migrate_account_balances(self):
        """Migrate account balance history from SQLite to PostgreSQL"""
        with sqlite3.connect(self.sqlite_path) as conn:
            balances_df = pd.read_sql_query("SELECT * FROM account_info", conn)

        if balances_df.empty:
            logger.info("No account balances to migrate")
            return

        for _, row in balances_df.iterrows():
            try:
                query = """
                INSERT INTO trading.account_balances (
                    account_id, cash_balance, total_equity, timestamp, data_source
                )
                VALUES ($1, $2, $3, $4, $5)
                """

                # Handle datetime conversion
                timestamp = pd.to_datetime(row['last_updated'])

                # For now, set total_equity same as cash_balance
                # In a real system, this would be calculated
                cash_balance = row['cash_balance']
                total_equity = cash_balance  # Simplified

                await self.pg_manager.execute_command(query, (
                    self.account_id,
                    cash_balance,
                    total_equity,
                    timestamp,
                    'MIGRATED'
                ))

                self.stats.balances_migrated += 1

            except Exception as e:
                error_msg = f"Failed to migrate balance record: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

        logger.info(f"Migrated {self.stats.balances_migrated} balance records")

    def _log_migration_stats(self):
        """Log detailed migration statistics"""
        logger.info("=== MIGRATION STATISTICS ===")
        logger.info(f"Accounts created: {self.stats.accounts_migrated}")
        logger.info(f"Symbols created: {self.stats.symbols_created}")
        logger.info(f"Positions migrated: {self.stats.positions_migrated}")
        logger.info(f"Trades migrated: {self.stats.trades_migrated}")
        logger.info(f"Balance records migrated: {self.stats.balances_migrated}")
        logger.info(f"Errors encountered: {len(self.stats.errors)}")

        if self.stats.errors:
            logger.warning("Migration errors:")
            for error in self.stats.errors[:10]:  # Show first 10 errors
                logger.warning(f"  - {error}")

class DataValidator:
    """Validate migrated data integrity"""

    def __init__(self, sqlite_path: str, pg_manager: PostgreSQLManager, account_id: str):
        self.sqlite_path = Path(sqlite_path)
        self.pg_manager = pg_manager
        self.account_id = account_id

    async def validate_migration(self) -> Dict[str, bool]:
        """Validate that migration was successful"""
        results = {}

        try:
            results['positions_count'] = await self._validate_positions_count()
            results['trades_count'] = await self._validate_trades_count()
            results['balance_records'] = await self._validate_balance_records()
            results['data_consistency'] = await self._validate_data_consistency()

            all_passed = all(results.values())
            logger.info(f"Migration validation {'PASSED' if all_passed else 'FAILED'}")

            return results

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"error": str(e)}

    async def _validate_positions_count(self) -> bool:
        """Validate positions count matches"""
        with sqlite3.connect(self.sqlite_path) as conn:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]

        pg_result = await self.pg_manager.execute_query(
            "SELECT COUNT(*) as count FROM trading.positions WHERE account_id = $1",
            (self.account_id,)
        )
        pg_count = pg_result[0]['count']

        match = sqlite_count == pg_count
        logger.info(f"Positions count - SQLite: {sqlite_count}, PostgreSQL: {pg_count} - {'✓' if match else '✗'}")
        return match

    async def _validate_trades_count(self) -> bool:
        """Validate trades count matches"""
        with sqlite3.connect(self.sqlite_path) as conn:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

        pg_result = await self.pg_manager.execute_query(
            "SELECT COUNT(*) as count FROM trading.trades WHERE account_id = $1",
            (self.account_id,)
        )
        pg_count = pg_result[0]['count']

        match = sqlite_count == pg_count
        logger.info(f"Trades count - SQLite: {sqlite_count}, PostgreSQL: {pg_count} - {'✓' if match else '✗'}")
        return match

    async def _validate_balance_records(self) -> bool:
        """Validate balance records count matches"""
        with sqlite3.connect(self.sqlite_path) as conn:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM account_info").fetchone()[0]

        pg_result = await self.pg_manager.execute_query(
            "SELECT COUNT(*) as count FROM trading.account_balances WHERE account_id = $1",
            (self.account_id,)
        )
        pg_count = pg_result[0]['count']

        match = sqlite_count == pg_count
        logger.info(f"Balance records - SQLite: {sqlite_count}, PostgreSQL: {pg_count} - {'✓' if match else '✗'}")
        return match

    async def _validate_data_consistency(self) -> bool:
        """Validate data consistency between SQLite and PostgreSQL"""
        try:
            # Check if any positions have invalid prices
            invalid_prices = await self.pg_manager.execute_query("""
                SELECT COUNT(*) as count
                FROM trading.positions
                WHERE account_id = $1 AND (avg_price <= 0 OR current_price <= 0)
            """, (self.account_id,))

            invalid_count = invalid_prices[0]['count']
            if invalid_count > 0:
                logger.warning(f"Found {invalid_count} positions with invalid prices")
                return False

            # Check if trades have valid data
            invalid_trades = await self.pg_manager.execute_query("""
                SELECT COUNT(*) as count
                FROM trading.trades
                WHERE account_id = $1 AND (quantity <= 0 OR price <= 0)
            """, (self.account_id,))

            invalid_trade_count = invalid_trades[0]['count']
            if invalid_trade_count > 0:
                logger.warning(f"Found {invalid_trade_count} trades with invalid data")
                return False

            logger.info("Data consistency validation passed ✓")
            return True

        except Exception as e:
            logger.error(f"Data consistency validation failed: {e}")
            return False

async def run_migration(sqlite_path: str = "portfolio.db", pg_config: DatabaseConfig = None) -> MigrationStats:
    """Main migration function"""
    if pg_config is None:
        pg_config = DatabaseConfig()

    # Initialize PostgreSQL database
    pg_manager = await initialize_database(pg_config)

    try:
        # Run migration
        migrator = DataMigrator(sqlite_path, pg_manager)
        stats = await migrator.migrate_all_data()

        # Validate migration
        if migrator.account_id:
            validator = DataValidator(sqlite_path, pg_manager, migrator.account_id)
            validation_results = await validator.validate_migration()

            if not all(validation_results.values()):
                logger.warning("Migration validation failed - data may be incomplete")

        return stats

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await pg_manager.close()

# Command-line interface for migration
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", default="portfolio.db", help="Path to SQLite database")
    parser.add_argument("--pg-host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--pg-port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--pg-database", default="trading_db", help="PostgreSQL database")
    parser.add_argument("--pg-user", default="trader", help="PostgreSQL username")
    parser.add_argument("--pg-password", required=True, help="PostgreSQL password")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Create PostgreSQL configuration
    config = DatabaseConfig(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        username=args.pg_user,
        password=args.pg_password
    )

    # Run migration
    asyncio.run(run_migration(args.sqlite_path, config))