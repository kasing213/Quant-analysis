"""
Data Validation and Quality Assurance Framework
Ensures data integrity and quality for quantitative trading applications
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from decimal import Decimal, InvalidOperation

from .pg_config import PostgreSQLManager, get_database_manager

logger = logging.getLogger(__name__)

@dataclass
class ValidationRule:
    """Definition of a data validation rule"""
    name: str
    description: str
    query: str
    expected_result: Any
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    fix_query: Optional[str] = None

@dataclass
class ValidationResult:
    """Result of a validation check"""
    rule_name: str
    passed: bool
    actual_result: Any
    expected_result: Any
    severity: str
    message: str
    fix_applied: bool = False

class DataValidator:
    """Comprehensive data validation for trading database"""

    def __init__(self, db_manager: PostgreSQLManager = None):
        self.db_manager = db_manager or get_database_manager()
        self.validation_rules = self._initialize_validation_rules()

    def _initialize_validation_rules(self) -> List[ValidationRule]:
        """Initialize standard validation rules"""
        return [
            # ===== ACCOUNT VALIDATION =====
            ValidationRule(
                name="accounts_have_valid_initial_capital",
                description="All accounts must have positive initial capital",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.accounts
                    WHERE initial_capital <= 0 OR initial_capital IS NULL
                """,
                expected_result=0,
                severity="ERROR",
                fix_query="""
                    UPDATE trading.accounts
                    SET initial_capital = 100000
                    WHERE initial_capital <= 0 OR initial_capital IS NULL
                """
            ),

            ValidationRule(
                name="accounts_have_valid_types",
                description="Account types must be valid",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.accounts
                    WHERE account_type NOT IN ('PAPER', 'LIVE', 'DEMO')
                """,
                expected_result=0,
                severity="ERROR"
            ),

            # ===== POSITION VALIDATION =====
            ValidationRule(
                name="positions_have_positive_avg_price",
                description="All positions must have positive average prices",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.positions
                    WHERE avg_price <= 0 AND is_active = TRUE
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="positions_have_consistent_market_value",
                description="Position market values should be consistent with quantity and price",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.positions
                    WHERE is_active = TRUE
                        AND current_price IS NOT NULL
                        AND ABS(market_value - (quantity * current_price)) > 0.01
                """,
                expected_result=0,
                severity="WARNING"
            ),

            ValidationRule(
                name="positions_have_valid_symbols",
                description="All positions should reference valid symbols",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.positions p
                    LEFT JOIN trading.symbols s ON p.symbol = s.symbol
                    WHERE p.is_active = TRUE AND s.symbol IS NULL
                """,
                expected_result=0,
                severity="WARNING",
                fix_query="""
                    INSERT INTO trading.symbols (symbol, security_type)
                    SELECT DISTINCT p.symbol, 'STK'
                    FROM trading.positions p
                    LEFT JOIN trading.symbols s ON p.symbol = s.symbol
                    WHERE s.symbol IS NULL
                    ON CONFLICT (symbol) DO NOTHING
                """
            ),

            # ===== TRADE VALIDATION =====
            ValidationRule(
                name="trades_have_positive_prices",
                description="All trades must have positive prices",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.trades
                    WHERE price <= 0
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="trades_have_positive_quantities",
                description="All trades must have positive quantities",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.trades
                    WHERE quantity <= 0
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="trades_have_valid_sides",
                description="Trade sides must be BUY or SELL",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.trades
                    WHERE side NOT IN ('BUY', 'SELL', 'SHORT', 'COVER')
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="trades_consistent_values",
                description="Trade values should be consistent with price and quantity",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.trades
                    WHERE ABS(trade_value - (quantity * price)) > 0.01
                """,
                expected_result=0,
                severity="WARNING"
            ),

            # ===== BALANCE VALIDATION =====
            ValidationRule(
                name="balances_non_negative_cash",
                description="Cash balances should generally be non-negative",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.account_balances
                    WHERE cash_balance < -10000  -- Allow some overdraft
                """,
                expected_result=0,
                severity="WARNING"
            ),

            ValidationRule(
                name="balances_consistent_equity",
                description="Total equity should be reasonable relative to cash",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.account_balances
                    WHERE total_equity < 0 OR total_equity > 10000000  -- Sanity check
                """,
                expected_result=0,
                severity="WARNING"
            ),

            # ===== MARKET DATA VALIDATION =====
            ValidationRule(
                name="daily_prices_valid_ohlc",
                description="Daily prices should have valid OHLC relationships",
                query="""
                    SELECT COUNT(*) as count
                    FROM market_data.daily_prices
                    WHERE high_price < low_price
                        OR high_price < open_price
                        OR high_price < close_price
                        OR low_price > open_price
                        OR low_price > close_price
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="daily_prices_positive_values",
                description="Daily prices should be positive",
                query="""
                    SELECT COUNT(*) as count
                    FROM market_data.daily_prices
                    WHERE open_price <= 0 OR high_price <= 0 OR low_price <= 0 OR close_price <= 0
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="no_future_prices",
                description="Price dates should not be in the future",
                query="""
                    SELECT COUNT(*) as count
                    FROM market_data.daily_prices
                    WHERE price_date > CURRENT_DATE
                """,
                expected_result=0,
                severity="ERROR"
            ),

            # ===== REFERENTIAL INTEGRITY =====
            ValidationRule(
                name="orphaned_positions",
                description="Positions should reference valid accounts",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.positions p
                    LEFT JOIN trading.accounts a ON p.account_id = a.account_id
                    WHERE a.account_id IS NULL
                """,
                expected_result=0,
                severity="ERROR"
            ),

            ValidationRule(
                name="orphaned_trades",
                description="Trades should reference valid accounts",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.trades t
                    LEFT JOIN trading.accounts a ON t.account_id = a.account_id
                    WHERE a.account_id IS NULL
                """,
                expected_result=0,
                severity="ERROR"
            ),

            # ===== BUSINESS LOGIC VALIDATION =====
            ValidationRule(
                name="position_trade_consistency",
                description="Position quantities should be consistent with trade history",
                query="""
                    WITH position_from_trades AS (
                        SELECT
                            account_id,
                            symbol,
                            SUM(CASE WHEN side IN ('BUY', 'COVER') THEN quantity ELSE -quantity END) as calculated_quantity
                        FROM trading.trades
                        GROUP BY account_id, symbol
                    )
                    SELECT COUNT(*) as count
                    FROM trading.positions p
                    JOIN position_from_trades pft ON p.account_id = pft.account_id AND p.symbol = pft.symbol
                    WHERE p.is_active = TRUE
                        AND ABS(p.quantity - pft.calculated_quantity) > 0  -- Allow small differences
                """,
                expected_result=0,
                severity="WARNING"
            ),

            # ===== DATA QUALITY CHECKS =====
            ValidationRule(
                name="duplicate_daily_prices",
                description="Should not have duplicate daily prices for same symbol/date",
                query="""
                    SELECT COUNT(*) as count
                    FROM (
                        SELECT symbol, price_date, COUNT(*) as cnt
                        FROM market_data.daily_prices
                        GROUP BY symbol, price_date
                        HAVING COUNT(*) > 1
                    ) duplicates
                """,
                expected_result=0,
                severity="WARNING"
            ),

            ValidationRule(
                name="stale_position_prices",
                description="Position prices should not be too stale",
                query="""
                    SELECT COUNT(*) as count
                    FROM trading.positions
                    WHERE is_active = TRUE
                        AND quantity != 0
                        AND (last_updated < CURRENT_TIMESTAMP - INTERVAL '7 days'
                             OR last_updated IS NULL)
                """,
                expected_result=0,
                severity="INFO"
            ),
        ]

    async def run_all_validations(self, fix_errors: bool = False) -> List[ValidationResult]:
        """Run all validation rules"""
        results = []

        logger.info(f"Running {len(self.validation_rules)} validation rules...")

        for rule in self.validation_rules:
            try:
                result = await self._run_validation_rule(rule, fix_errors)
                results.append(result)
            except Exception as e:
                logger.error(f"Validation rule {rule.name} failed: {e}")
                results.append(ValidationResult(
                    rule_name=rule.name,
                    passed=False,
                    actual_result=f"ERROR: {e}",
                    expected_result=rule.expected_result,
                    severity="ERROR",
                    message=f"Validation rule execution failed: {e}"
                ))

        # Summary
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        errors = sum(1 for r in results if r.severity == 'ERROR' and not r.passed)
        warnings = sum(1 for r in results if r.severity == 'WARNING' and not r.passed)

        logger.info(f"Validation complete: {passed}/{total} passed, {errors} errors, {warnings} warnings")

        return results

    async def _run_validation_rule(self, rule: ValidationRule, fix_errors: bool = False) -> ValidationResult:
        """Run a single validation rule"""
        # Execute validation query
        result = await self.db_manager.execute_query(rule.query)
        actual_result = result[0]['count'] if result and 'count' in result[0] else result

        # Check if validation passed
        passed = actual_result == rule.expected_result

        # Prepare result message
        if passed:
            message = f"✓ {rule.description}"
        else:
            message = f"✗ {rule.description} (Expected: {rule.expected_result}, Actual: {actual_result})"

        validation_result = ValidationResult(
            rule_name=rule.name,
            passed=passed,
            actual_result=actual_result,
            expected_result=rule.expected_result,
            severity=rule.severity,
            message=message
        )

        # Apply fix if requested and available
        if not passed and fix_errors and rule.fix_query and rule.severity == "ERROR":
            try:
                await self.db_manager.execute_command(rule.fix_query)
                validation_result.fix_applied = True
                logger.info(f"Applied fix for rule: {rule.name}")
            except Exception as e:
                logger.warning(f"Failed to apply fix for rule {rule.name}: {e}")

        return validation_result

    async def validate_account_data(self, account_id: str) -> Dict[str, Any]:
        """Validate data for a specific account"""
        validation_queries = {
            'position_count': "SELECT COUNT(*) as count FROM trading.positions WHERE account_id = $1 AND is_active = TRUE",
            'trade_count': "SELECT COUNT(*) as count FROM trading.trades WHERE account_id = $1",
            'balance_records': "SELECT COUNT(*) as count FROM trading.account_balances WHERE account_id = $1",
            'negative_positions': """
                SELECT COUNT(*) as count
                FROM trading.positions
                WHERE account_id = $1 AND is_active = TRUE AND (avg_price <= 0 OR current_price < 0)
            """,
            'invalid_trades': """
                SELECT COUNT(*) as count
                FROM trading.trades
                WHERE account_id = $1 AND (price <= 0 OR quantity <= 0)
            """,
            'position_value_sum': """
                SELECT COALESCE(SUM(market_value), 0) as total
                FROM trading.positions
                WHERE account_id = $1 AND is_active = TRUE
            """,
            'latest_balance': """
                SELECT cash_balance, total_equity
                FROM trading.account_balances
                WHERE account_id = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """
        }

        results = {}

        for key, query in validation_queries.items():
            try:
                result = await self.db_manager.execute_query(query, (account_id,))
                if result:
                    if 'count' in result[0]:
                        results[key] = result[0]['count']
                    elif 'total' in result[0]:
                        results[key] = float(result[0]['total'])
                    else:
                        results[key] = dict(result[0])
                else:
                    results[key] = 0
            except Exception as e:
                logger.error(f"Failed to execute validation query {key}: {e}")
                results[key] = f"ERROR: {e}"

        return results

    async def check_data_consistency(self, account_id: str) -> Dict[str, bool]:
        """Check data consistency for an account"""
        consistency_checks = {}

        try:
            # Check position-trade consistency
            trade_summary = await self.db_manager.execute_query("""
                SELECT
                    symbol,
                    SUM(CASE WHEN side IN ('BUY', 'COVER') THEN quantity ELSE -quantity END) as net_quantity
                FROM trading.trades
                WHERE account_id = $1
                GROUP BY symbol
            """, (account_id,))

            position_summary = await self.db_manager.execute_query("""
                SELECT symbol, quantity
                FROM trading.positions
                WHERE account_id = $1 AND is_active = TRUE
            """, (account_id,))

            # Convert to dictionaries for comparison
            trade_quantities = {row['symbol']: row['net_quantity'] for row in trade_summary}
            position_quantities = {row['symbol']: row['quantity'] for row in position_summary}

            # Check consistency
            symbols = set(trade_quantities.keys()) | set(position_quantities.keys())
            consistent_positions = 0
            total_positions = len(symbols)

            for symbol in symbols:
                trade_qty = trade_quantities.get(symbol, 0)
                position_qty = position_quantities.get(symbol, 0)

                if trade_qty == position_qty:
                    consistent_positions += 1

            consistency_checks['position_trade_consistency'] = consistent_positions == total_positions

            # Check balance consistency (simplified)
            latest_balance = await self.db_manager.execute_query("""
                SELECT total_equity, cash_balance
                FROM trading.account_balances
                WHERE account_id = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, (account_id,))

            if latest_balance:
                equity = float(latest_balance[0]['total_equity'])
                cash = float(latest_balance[0]['cash_balance'])
                consistency_checks['positive_equity'] = equity > 0
                consistency_checks['reasonable_cash_ratio'] = cash / equity < 2.0 if equity > 0 else True
            else:
                consistency_checks['positive_equity'] = False
                consistency_checks['reasonable_cash_ratio'] = False

        except Exception as e:
            logger.error(f"Data consistency check failed: {e}")
            consistency_checks['error'] = str(e)

        return consistency_checks

    async def generate_data_quality_report(self, account_id: str = None) -> Dict[str, Any]:
        """Generate comprehensive data quality report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'account_id': account_id,
            'validation_results': [],
            'summary': {},
            'recommendations': []
        }

        # Run all validations
        validation_results = await self.run_all_validations()
        report['validation_results'] = [
            {
                'rule': r.rule_name,
                'passed': r.passed,
                'severity': r.severity,
                'message': r.message,
                'fix_applied': r.fix_applied
            }
            for r in validation_results
        ]

        # Summary statistics
        total_rules = len(validation_results)
        passed_rules = sum(1 for r in validation_results if r.passed)
        error_count = sum(1 for r in validation_results if r.severity == 'ERROR' and not r.passed)
        warning_count = sum(1 for r in validation_results if r.severity == 'WARNING' and not r.passed)

        report['summary'] = {
            'total_rules': total_rules,
            'passed_rules': passed_rules,
            'pass_rate': passed_rules / total_rules * 100 if total_rules > 0 else 0,
            'errors': error_count,
            'warnings': warning_count,
            'overall_health': 'GOOD' if error_count == 0 and warning_count <= 2 else 'NEEDS_ATTENTION' if error_count == 0 else 'CRITICAL'
        }

        # Account-specific checks if provided
        if account_id:
            account_validation = await self.validate_account_data(account_id)
            consistency_checks = await self.check_data_consistency(account_id)

            report['account_validation'] = account_validation
            report['consistency_checks'] = consistency_checks

        # Generate recommendations
        if error_count > 0:
            report['recommendations'].append("Address critical data errors immediately")
        if warning_count > 5:
            report['recommendations'].append("Review data quality warnings and consider cleanup")

        failed_rules = [r for r in validation_results if not r.passed]
        if any(r.rule_name.endswith('prices') for r in failed_rules):
            report['recommendations'].append("Review price data quality and update mechanisms")
        if any(r.rule_name.endswith('consistency') for r in failed_rules):
            report['recommendations'].append("Investigate data consistency issues between related tables")

        return report

class DataCleaner:
    """Data cleaning utilities"""

    def __init__(self, db_manager: PostgreSQLManager = None):
        self.db_manager = db_manager or get_database_manager()

    async def clean_stale_positions(self, days_threshold: int = 30) -> int:
        """Clean up stale position records"""
        query = """
        UPDATE trading.positions
        SET is_active = FALSE
        WHERE is_active = TRUE
            AND quantity = 0
            AND last_updated < CURRENT_TIMESTAMP - INTERVAL '%s days'
        """

        result = await self.db_manager.execute_command(query % days_threshold)
        # Extract number from result string like "UPDATE 5"
        cleaned_count = int(result.split()[-1]) if result and result.split() else 0

        logger.info(f"Cleaned {cleaned_count} stale position records")
        return cleaned_count

    async def fix_missing_symbols(self) -> int:
        """Create missing symbol records referenced by positions/trades"""
        query = """
        INSERT INTO trading.symbols (symbol, security_type, is_active)
        SELECT DISTINCT p.symbol, 'STK', TRUE
        FROM trading.positions p
        LEFT JOIN trading.symbols s ON p.symbol = s.symbol
        WHERE s.symbol IS NULL
        ON CONFLICT (symbol) DO NOTHING
        """

        result = await self.db_manager.execute_command(query)
        created_count = int(result.split()[-1]) if result and result.split() else 0

        logger.info(f"Created {created_count} missing symbol records")
        return created_count

    async def recalculate_position_values(self, account_id: str) -> int:
        """Recalculate position market values and P&L"""
        query = """
        UPDATE trading.positions
        SET last_updated = CURRENT_TIMESTAMP
        WHERE account_id = $1 AND is_active = TRUE AND current_price IS NOT NULL
        """

        result = await self.db_manager.execute_command(query, (account_id,))
        updated_count = int(result.split()[-1]) if result and result.split() else 0

        logger.info(f"Recalculated values for {updated_count} positions")
        return updated_count

# Utility functions
async def run_data_validation(account_id: str = None, fix_errors: bool = False) -> Dict[str, Any]:
    """Convenience function to run data validation"""
    validator = DataValidator()
    report = await validator.generate_data_quality_report(account_id)

    if fix_errors:
        # Apply fixes
        await validator.run_all_validations(fix_errors=True)
        # Re-run validation to check fixes
        updated_report = await validator.generate_data_quality_report(account_id)
        report['after_fixes'] = updated_report['summary']

    return report

async def clean_database_data() -> Dict[str, int]:
    """Convenience function to clean database data"""
    cleaner = DataCleaner()

    results = {}
    results['stale_positions'] = await cleaner.clean_stale_positions()
    results['missing_symbols'] = await cleaner.fix_missing_symbols()

    return results