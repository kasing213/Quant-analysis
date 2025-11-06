"""
PostgreSQL Database Setup and Initialization Script
Automates the complete setup process for the quantitative trading database
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import argparse
import getpass

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.database.pg_config import DatabaseConfig, PostgreSQLManager, DatabaseInitializer, initialize_database
from src.database.migration import run_migration
from src.database.validation import run_data_validation, clean_database_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('database_setup.log')
    ]
)
logger = logging.getLogger(__name__)

class DatabaseSetup:
    """Complete database setup orchestrator"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.db_manager = None

    async def setup_complete_database(self, migrate_from_sqlite: bool = False,
                                    sqlite_path: str = "portfolio.db") -> Dict[str, Any]:
        """Complete database setup process"""
        setup_results = {
            'database_created': False,
            'schema_initialized': False,
            'data_migrated': False,
            'validation_passed': False,
            'performance_optimized': False,
            'errors': []
        }

        try:
            logger.info("Starting complete database setup...")

            # Step 1: Initialize database and schema
            logger.info("Step 1: Initializing database and schema...")
            self.db_manager = await initialize_database(self.config)
            setup_results['database_created'] = True
            setup_results['schema_initialized'] = True

            # Step 2: Migrate data from SQLite if requested
            if migrate_from_sqlite:
                logger.info("Step 2: Migrating data from SQLite...")
                if Path(sqlite_path).exists():
                    migration_stats = await run_migration(sqlite_path, self.config)
                    setup_results['data_migrated'] = True
                    setup_results['migration_stats'] = {
                        'accounts': migration_stats.accounts_migrated,
                        'positions': migration_stats.positions_migrated,
                        'trades': migration_stats.trades_migrated,
                        'balances': migration_stats.balances_migrated,
                        'errors': len(migration_stats.errors)
                    }
                else:
                    logger.warning(f"SQLite database not found at {sqlite_path}")
                    setup_results['errors'].append(f"SQLite database not found: {sqlite_path}")

            # Step 3: Apply performance optimizations
            logger.info("Step 3: Applying performance optimizations...")
            await self._apply_performance_settings()
            setup_results['performance_optimized'] = True

            # Step 4: Run data validation
            logger.info("Step 4: Running data validation...")
            validation_report = await run_data_validation(fix_errors=True)
            setup_results['validation_passed'] = validation_report['summary']['overall_health'] != 'CRITICAL'
            setup_results['validation_report'] = validation_report

            # Step 5: Create sample data if no migration occurred
            if not migrate_from_sqlite:
                logger.info("Step 5: Creating sample data...")
                await self._create_sample_data()

            logger.info("Database setup completed successfully!")

        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            setup_results['errors'].append(str(e))
            raise

        finally:
            if self.db_manager:
                await self.db_manager.close()

        return setup_results

    async def _apply_performance_settings(self):
        """Apply performance optimization settings"""
        try:
            # Read and execute performance tuning SQL
            perf_sql_path = Path(__file__).parent / 'performance_tuning.sql'
            if perf_sql_path.exists():
                with open(perf_sql_path, 'r') as f:
                    performance_sql = f.read()

                # Split and execute commands
                commands = [cmd.strip() for cmd in performance_sql.split(';') if cmd.strip()]

                for command in commands:
                    if command and not command.startswith('--'):
                        try:
                            await self.db_manager.execute_command(command)
                        except Exception as e:
                            # Some commands may fail due to permissions or existing settings
                            logger.warning(f"Performance setting command failed (may be expected): {e}")

                logger.info("Performance settings applied")
            else:
                logger.warning("Performance tuning SQL file not found")

        except Exception as e:
            logger.error(f"Failed to apply performance settings: {e}")
            # Don't raise here as this is not critical

    async def _create_sample_data(self):
        """Create sample data for testing"""
        try:
            # Create sample account
            account_query = """
            INSERT INTO trading.accounts (account_name, account_type, initial_capital, currency)
            VALUES ('Demo Account', 'PAPER', 100000.00, 'USD')
            ON CONFLICT DO NOTHING
            RETURNING account_id
            """

            result = await self.db_manager.execute_query(account_query)
            if result:
                account_id = result[0]['account_id']

                # Create initial balance
                balance_query = """
                INSERT INTO trading.account_balances (account_id, cash_balance, total_equity)
                VALUES ($1, 100000.00, 100000.00)
                """
                await self.db_manager.execute_command(balance_query, (account_id,))

                # Create sample symbols
                symbols_data = [
                    ('AAPL', 'Apple Inc.', 'Technology', 'Hardware'),
                    ('NVDA', 'NVIDIA Corporation', 'Technology', 'Semiconductors'),
                    ('TSLA', 'Tesla, Inc.', 'Consumer Cyclical', 'Auto Manufacturers'),
                    ('SPY', 'SPDR S&P 500 ETF', 'Financial Services', 'Asset Management'),
                    ('QQQ', 'Invesco QQQ Trust', 'Financial Services', 'Asset Management'),
                ]

                symbol_query = """
                INSERT INTO trading.symbols (symbol, company_name, sector, industry)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (symbol) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    sector = EXCLUDED.sector,
                    industry = EXCLUDED.industry
                """

                for symbol_data in symbols_data:
                    await self.db_manager.execute_command(symbol_query, symbol_data)

                logger.info("Sample data created successfully")

        except Exception as e:
            logger.error(f"Failed to create sample data: {e}")

def get_database_config() -> DatabaseConfig:
    """Get database configuration from environment or user input"""
    # Try environment variables first
    config = DatabaseConfig()

    # If key environment variables are not set, prompt user
    if not os.getenv('POSTGRES_PASSWORD'):
        print("\n=== PostgreSQL Database Configuration ===")
        print(f"Host: {config.host}")
        print(f"Port: {config.port}")
        print(f"Database: {config.database}")
        print(f"Username: {config.username}")

        # Get password securely
        password = getpass.getpass("PostgreSQL password: ")
        config.password = password

        # Ask for other settings
        response = input(f"Use different host than '{config.host}'? (y/N): ")
        if response.lower() == 'y':
            config.host = input("PostgreSQL host: ")

        response = input(f"Use different database name than '{config.database}'? (y/N): ")
        if response.lower() == 'y':
            config.database = input("Database name: ")

    return config

async def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="PostgreSQL Database Setup for Trading System")
    parser.add_argument('--migrate', action='store_true', help='Migrate data from SQLite')
    parser.add_argument('--sqlite-path', default='portfolio.db', help='Path to SQLite database')
    parser.add_argument('--host', help='PostgreSQL host')
    parser.add_argument('--port', type=int, help='PostgreSQL port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--user', help='PostgreSQL username')
    parser.add_argument('--password', help='PostgreSQL password')
    parser.add_argument('--skip-validation', action='store_true', help='Skip data validation')
    parser.add_argument('--sample-data', action='store_true', help='Create sample data')

    args = parser.parse_args()

    # Get database configuration
    config = DatabaseConfig()

    # Override with command line arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.database:
        config.database = args.database
    if args.user:
        config.username = args.user
    if args.password:
        config.password = args.password

    # Get password if not provided
    if not config.password:
        config.password = getpass.getpass("PostgreSQL password: ")

    print("\n=== Database Setup Configuration ===")
    print(f"Host: {config.host}:{config.port}")
    print(f"Database: {config.database}")
    print(f"Username: {config.username}")
    print(f"Migration: {'Yes' if args.migrate else 'No'}")
    if args.migrate:
        print(f"SQLite path: {args.sqlite_path}")
    print("=" * 40)

    confirm = input("\nProceed with setup? (y/N): ")
    if confirm.lower() != 'y':
        print("Setup cancelled.")
        return

    try:
        # Run setup
        setup = DatabaseSetup(config)
        results = await setup.setup_complete_database(
            migrate_from_sqlite=args.migrate,
            sqlite_path=args.sqlite_path
        )

        # Print results
        print("\n=== Setup Results ===")
        print(f"Database created: {'✓' if results['database_created'] else '✗'}")
        print(f"Schema initialized: {'✓' if results['schema_initialized'] else '✗'}")
        print(f"Data migrated: {'✓' if results['data_migrated'] else 'N/A'}")
        print(f"Performance optimized: {'✓' if results['performance_optimized'] else '✗'}")
        print(f"Validation passed: {'✓' if results['validation_passed'] else '✗'}")

        if results.get('migration_stats'):
            stats = results['migration_stats']
            print(f"\nMigration Statistics:")
            print(f"  Accounts: {stats['accounts']}")
            print(f"  Positions: {stats['positions']}")
            print(f"  Trades: {stats['trades']}")
            print(f"  Balance records: {stats['balances']}")
            if stats['errors'] > 0:
                print(f"  Errors: {stats['errors']}")

        if results['errors']:
            print(f"\nErrors encountered: {len(results['errors'])}")
            for error in results['errors']:
                print(f"  - {error}")

        if not results['validation_passed']:
            print("\n⚠️  Data validation issues found. Check the validation report.")

        print("\n✅ Database setup completed!")
        print(f"\nConnection string: postgresql://{config.username}:***@{config.host}:{config.port}/{config.database}")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())