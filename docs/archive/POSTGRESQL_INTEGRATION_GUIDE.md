# PostgreSQL Database Integration Guide
## Complete Implementation Guide for Quantitative Trading System

This guide provides comprehensive instructions for integrating PostgreSQL database functionality into your TikTok analyzing (quantitative trading) project.

## 🎯 Overview

Your project has been enhanced with a production-ready PostgreSQL database system that provides:

- **Scalable Data Storage**: Handles large volumes of trading data efficiently
- **Advanced Analytics**: Complex queries and real-time performance metrics
- **Data Integrity**: Comprehensive validation and quality assurance
- **High Performance**: Optimized for quantitative analysis workloads
- **Real-time Capabilities**: Live price updates and portfolio tracking

## 📁 New File Structure

```
/mnt/d/Tiktok-analyzing/
├── database/                      # NEW: PostgreSQL Integration
│   ├── schema.sql                 # Database schema definition
│   ├── pg_config.py              # Connection management
│   ├── data_access.py            # High-level data access layer
│   ├── migration.py              # SQLite to PostgreSQL migration
│   ├── validation.py             # Data quality assurance
│   ├── performance_tuning.sql    # Performance optimizations
│   └── setup.py                  # Automated setup script
├── core/
│   └── pg_portfolio_manager.py   # NEW: Enhanced portfolio manager
├── .env.postgresql               # NEW: Environment configuration template
├── requirements_postgresql.txt   # NEW: Enhanced dependencies
└── [existing files remain unchanged]
```

## 🚀 Quick Start

### 1. Install PostgreSQL Dependencies

```bash
# Install new requirements
pip install -r requirements_postgresql.txt

# Or install core PostgreSQL packages only
pip install asyncpg psycopg2-binary pandas numpy
```

### 2. Set Up PostgreSQL Database

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Or on macOS with Homebrew
brew install postgresql

# Start PostgreSQL service
sudo systemctl start postgresql  # Linux
brew services start postgresql   # macOS
```

### 3. Configure Environment

```bash
# Copy and customize environment configuration
cp .env.postgresql .env

# Edit .env with your database credentials
nano .env
```

### 4. Initialize Database

```bash
# Run automated setup (recommended)
python database/setup.py --migrate --sqlite-path portfolio.db

# Or manual setup
python -c "
import asyncio
from database.setup import DatabaseSetup, DatabaseConfig
config = DatabaseConfig()  # Uses .env values
setup = DatabaseSetup(config)
asyncio.run(setup.setup_complete_database(migrate_from_sqlite=True))
"
```

## 📊 Database Schema Overview

### Core Trading Tables

1. **trading.accounts**: Multi-account support with paper/live trading
2. **trading.positions**: Real-time position tracking with P&L calculations
3. **trading.trades**: Complete trade history with execution details
4. **trading.orders**: Order management and status tracking
5. **trading.account_balances**: Historical balance tracking

### Market Data Tables

1. **market_data.daily_prices**: Historical OHLCV data with dividends/splits
2. **market_data.intraday_prices**: High-frequency price data (partitioned)
3. **market_data.market_snapshots**: Real-time market data snapshots

### Analytics Tables

1. **analytics.portfolio_snapshots**: Daily portfolio performance history
2. **analytics.risk_metrics**: Risk calculations and VaR metrics
3. **backtesting.backtest_runs**: Strategy backtesting configurations
4. **backtesting.backtest_results**: Performance results and statistics

## 🔧 Integration with Existing Code

### Replace SQLite Portfolio Manager

```python
# OLD: SQLite-based portfolio manager
from core.portfolio_manager import PortfolioManager

# NEW: PostgreSQL-based portfolio manager
from core.pg_portfolio_manager import PostgreSQLPortfolioManager, create_portfolio_manager

# In your Streamlit app or main application:
async def initialize_app():
    # Create PostgreSQL-backed portfolio manager
    pm = await create_portfolio_manager(
        account_name="My Trading Account",
        initial_capital=100000.0,
        use_ib=True,
        paper_trading=True
    )
    return pm

# For Streamlit compatibility (synchronous initialization)
@st.cache_resource
def get_portfolio_manager():
    import asyncio
    return asyncio.run(initialize_app())
```

### Update Streamlit Application

```python
# In portfolio_tracker.py or similar
import asyncio
from core.pg_portfolio_manager import PostgreSQLPortfolioManager

# Update session state initialization
if 'portfolio_manager' not in st.session_state:
    # Initialize with PostgreSQL
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    pm = loop.run_until_complete(create_portfolio_manager(
        account_name="Streamlit Portfolio",
        initial_capital=100000,
        use_ib=True,
        paper_trading=True
    ))

    st.session_state.portfolio_manager = pm
```

## 🎛️ Configuration Options

### Environment Variables (.env)

```bash
# Database Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_db
POSTGRES_USER=trader
POSTGRES_PASSWORD=your_secure_password

# Connection Pool
POSTGRES_MIN_CONN=5
POSTGRES_MAX_CONN=25

# Performance
POSTGRES_TIMEOUT=30
POSTGRES_CACHE_SIZE=1024

# Application
DATABASE_TYPE=postgresql
DEFAULT_INITIAL_CAPITAL=100000.00
ENABLE_DATA_VALIDATION=true
```

### Database Configuration

```python
from database.pg_config import DatabaseConfig

# Custom configuration
config = DatabaseConfig(
    host='your-postgres-server.com',
    port=5432,
    database='trading_production',
    username='trader',
    password='secure_password',
    min_connections=10,
    max_connections=50
)
```

## 📈 Advanced Features

### 1. Real-time Price Updates

```python
# Automatic price updates for all positions
await portfolio_manager.update_prices()

# Update specific symbols
await portfolio_manager.update_prices(['AAPL', 'NVDA', 'TSLA'])
```

### 2. Portfolio Analytics

```python
# Get comprehensive portfolio summary
summary = await portfolio_manager.get_portfolio_summary()
print(f"Total Equity: ${summary.total_equity:,.2f}")
print(f"Total P&L: ${summary.total_pnl:,.2f} ({summary.total_pnl_pct:.2f}%)")
print(f"Sharpe Ratio: {summary.sharpe_ratio:.3f}")

# Risk metrics
risk_metrics = await portfolio_manager.get_risk_metrics()
print(f"Position Concentration: {risk_metrics['position_concentration']:.1f}%")
print(f"Long/Short Ratio: {risk_metrics['long_short_ratio']:.2f}")
```

### 3. Historical Performance Analysis

```python
# Get performance over time
performance_df = await portfolio_manager.get_portfolio_performance(days_back=90)

# Performance attribution by position
attribution = await portfolio_manager.get_performance_attribution()
for symbol, attr in attribution.items():
    print(f"{symbol}: {attr['pnl_contribution']:,.2f} ({attr['pnl_pct_contribution']:.1f}%)")
```

### 4. Data Validation and Quality Assurance

```python
from database.validation import run_data_validation, clean_database_data

# Run comprehensive data validation
validation_report = await run_data_validation(account_id="your-account-id")
print(f"Overall Health: {validation_report['summary']['overall_health']}")

# Clean up data issues
cleanup_results = await clean_database_data()
print(f"Cleaned {cleanup_results['stale_positions']} stale positions")
```

## 🔍 Migration Process

### Automatic Migration

```bash
# Migrate existing SQLite data
python database/setup.py --migrate --sqlite-path portfolio.db
```

### Manual Migration

```python
from database.migration import run_migration
from database.pg_config import DatabaseConfig

config = DatabaseConfig()  # Uses environment variables
stats = await run_migration("portfolio.db", config)

print(f"Migrated {stats.positions_migrated} positions")
print(f"Migrated {stats.trades_migrated} trades")
print(f"Migrated {stats.balances_migrated} balance records")
```

### Data Validation After Migration

```python
from database.validation import DataValidator

validator = DataValidator()
results = await validator.run_all_validations(fix_errors=True)

for result in results:
    if not result.passed and result.severity == 'ERROR':
        print(f"ERROR: {result.message}")
```

## 🚀 Performance Optimizations

### Implemented Optimizations

1. **Connection Pooling**: Efficient connection management
2. **Indexes**: Optimized for time-series and analytical queries
3. **Partitioning**: Large tables partitioned by date
4. **Materialized Views**: Pre-computed analytics
5. **Prepared Statements**: Cached query plans

### Performance Monitoring

```python
# Check database health
from database.validation import DataValidator

validator = DataValidator()
health_report = await validator.check_database_health()

for metric in health_report:
    print(f"{metric['metric_name']}: {metric['metric_value']} ({metric['status']})")
```

## 📊 Backtesting Integration

### Enhanced Backtesting with Database Storage

```python
from database.data_access import BacktestingDataAccess

backtest_access = BacktestingDataAccess()

# Store backtest configuration
run_id = await backtest_access.store_backtest_run(
    run_name="MA Crossover Test",
    strategy_name="MovingAverageStrategy",
    symbol="AAPL",
    start_date=datetime(2023, 1, 1).date(),
    end_date=datetime(2024, 1, 1).date(),
    initial_capital=100000.0,
    strategy_params={'fast_period': 10, 'slow_period': 30}
)

# Store results
await backtest_access.store_backtest_results(run_id, {
    'total_return_pct': 15.7,
    'sharpe_ratio': 1.24,
    'max_drawdown': -8.3,
    'win_rate': 58.3,
    'total_trades': 24
})

# Analyze strategy performance
performance_df = await backtest_access.get_strategy_performance()
```

## 🔒 Security Considerations

### Database Security

1. **Connection Security**: Use SSL in production
2. **User Permissions**: Create dedicated database users
3. **Password Security**: Use environment variables
4. **Network Security**: Restrict database access

### Application Security

```python
# Example production configuration
config = DatabaseConfig(
    host='db.production.com',
    ssl_mode='require',
    ssl_cert='/path/to/client-cert.pem',
    ssl_key='/path/to/client-key.pem',
    ssl_ca='/path/to/ca-cert.pem'
)
```

## 🛠️ Troubleshooting

### Common Issues

1. **Connection Errors**
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql

   # Check connection
   psql -h localhost -U trader -d trading_db
   ```

2. **Migration Issues**
   ```python
   # Check SQLite data
   import sqlite3
   conn = sqlite3.connect('portfolio.db')
   print(conn.execute('SELECT COUNT(*) FROM trades').fetchone())
   ```

3. **Performance Issues**
   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   WHERE mean_time > 100
   ORDER BY mean_time DESC;
   ```

### Logging and Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable database query logging
logger = logging.getLogger('database')
logger.setLevel(logging.DEBUG)
```

## 📚 API Reference

### Key Classes

- `PostgreSQLPortfolioManager`: Main portfolio management class
- `TradingDataAccess`: High-level trading data operations
- `MarketDataAccess`: Market data storage and retrieval
- `BacktestingDataAccess`: Backtesting data management
- `DataValidator`: Data quality and validation

### Key Functions

- `create_portfolio_manager()`: Factory function for portfolio manager
- `run_migration()`: Migrate data from SQLite
- `run_data_validation()`: Validate data integrity
- `initialize_database()`: Set up database and schema

## 🎯 Next Steps

1. **Install Dependencies**: Run `pip install -r requirements_postgresql.txt`
2. **Set Up Database**: Use `python database/setup.py --migrate`
3. **Update Application**: Replace SQLite calls with PostgreSQL equivalents
4. **Test Integration**: Verify data migration and functionality
5. **Performance Tuning**: Monitor and optimize based on usage patterns
6. **Production Deployment**: Configure SSL and security settings

## 📞 Support

- Check the validation framework for data integrity issues
- Use the logging system for troubleshooting
- Monitor performance with built-in health checks
- Review the migration logs for data transfer issues

This integration provides a robust, scalable foundation for your quantitative trading system with advanced analytics capabilities and production-ready performance optimizations.