"""
Pipeline-specific service configuration and credential management.

This module provides pipeline-aware configuration for service wiring,
ensuring that credentials, endpoints, and validations change automatically
based on the selected pipeline mode (paper vs live).
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

from .pipeline import Pipeline, get_current_pipeline

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Types of services that can be configured"""
    BINANCE_REST = "binance_rest"
    BINANCE_WEBSOCKET = "binance_websocket"
    BINANCE_DATA_MANAGER = "binance_data_manager"
    BOT_ORCHESTRATOR = "bot_orchestrator"
    DATABASE = "database"
    REDIS = "redis"


@dataclass
class BinanceConfig:
    """Binance-specific configuration"""
    api_key: str
    api_secret: str
    testnet: bool
    test_mode: bool
    base_url: str
    ws_base_url: str

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate Binance configuration"""
        if not self.test_mode:
            if not self.api_key or not self.api_secret:
                return False, "API key and secret required for live trading"
            if len(self.api_key) < 20 or len(self.api_secret) < 20:
                return False, "Invalid API credentials format"
        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for service initialization"""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "testnet": self.testnet,
            "test_mode": self.test_mode,
            "base_url": self.base_url,
            "ws_base_url": self.ws_base_url,
        }


@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str
    port: int
    password: Optional[str]
    db: int
    enabled: bool = True

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate Redis configuration.

        Returns True if Redis is disabled OR if configuration is valid.
        This allows the application to run without Redis.
        """
        if not self.enabled:
            return True, None

        if not self.host:
            # Redis is optional - return True to allow app to continue
            return True, None

        if self.host and not (1 <= self.port <= 65535):
            return False, "Invalid Redis port"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for service initialization"""
        return {
            "host": self.host,
            "port": self.port,
            "password": self.password,
            "db": self.db,
            "enabled": self.enabled,
        }


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str
    pool_size: int
    max_overflow: int

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate database configuration"""
        if not self.url or not self.url.startswith("postgresql"):
            return False, "Invalid PostgreSQL connection URL"
        if self.pool_size < 1:
            return False, "Pool size must be at least 1"
        return True, None


class PipelineServiceConfig:
    """
    Manages pipeline-specific service configurations.

    Provides automatic credential switching, service wiring configuration,
    and validation based on the selected pipeline mode.
    """

    def __init__(self, pipeline: Optional[Pipeline] = None):
        self.pipeline = pipeline or get_current_pipeline()
        logger.info(f"Initializing service config for pipeline: {self.pipeline.value}")

    def get_binance_config(self) -> Optional[BinanceConfig]:
        """
        Get Binance configuration for the current pipeline.

        Returns:
            BinanceConfig instance for Binance pipelines
        """
        # Determine if we're in paper or live mode
        is_paper = self.pipeline == Pipeline.BINANCE_PAPER

        # Read credentials from environment with pipeline-specific prefixes
        if is_paper:
            # Paper mode credentials
            api_key = os.getenv("BINANCE_TESTNET_API_KEY") or os.getenv("BINANCE_API_KEY", "")
            api_secret = os.getenv("BINANCE_TESTNET_API_SECRET") or os.getenv("BINANCE_API_SECRET", "")
            testnet = True
            test_mode = True
            base_url = "https://testnet.binance.vision/api"
            ws_base_url = "wss://testnet.binance.vision/ws"
        else:
            # Live mode credentials
            api_key = os.getenv("BINANCE_LIVE_API_KEY") or os.getenv("BINANCE_API_KEY", "")
            api_secret = os.getenv("BINANCE_LIVE_API_SECRET") or os.getenv("BINANCE_API_SECRET", "")
            testnet = False
            test_mode = os.getenv("BINANCE_TEST_MODE", "false").lower() == "true"
            base_url = "https://api.binance.com/api"
            ws_base_url = "wss://stream.binance.com:9443/ws"

        config = BinanceConfig(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            test_mode=test_mode,
            base_url=base_url,
            ws_base_url=ws_base_url,
        )

        return config

    def get_redis_config(self) -> RedisConfig:
        """
        Get Redis configuration for the current pipeline.

        Returns:
            RedisConfig with pipeline-specific database selection.
            Redis is optional - can be disabled via REDIS_ENABLED=false.
        """
        # Check if Redis is enabled
        redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        redis_host = os.getenv("REDIS_HOST", "")

        # Use different Redis databases for different pipelines
        db_map = {
            Pipeline.BINANCE_PAPER: 0,
            Pipeline.BINANCE_LIVE: 1,
        }

        return RedisConfig(
            host=redis_host,
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            db=db_map.get(self.pipeline, 0),
            enabled=redis_enabled and bool(redis_host),
        )

    def get_database_config(self) -> DatabaseConfig:
        """
        Get database configuration for the current pipeline.

        Note: Currently uses shared database with schema isolation.
        Could be extended to use separate databases per pipeline.
        """
        return DatabaseConfig(
            url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://trader:trading_secure_password_2024@localhost:5432/trading_db"
            ),
            pool_size=int(os.getenv("POSTGRES_MIN_CONN", "10")),
            max_overflow=int(os.getenv("POSTGRES_MAX_CONN", "25")),
        )

    def get_dashboard_symbols(self) -> list[str]:
        """
        Get dashboard symbols based on pipeline.

        Returns:
            List of symbols appropriate for the current pipeline
        """
        symbols_env = os.getenv("BINANCE_DASHBOARD_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT")

        symbols = [
            symbol.strip().upper()
            for symbol in symbols_env.split(",")
            if symbol.strip()
        ]

        return symbols or ["BTCUSDT", "ETHUSDT"]  # Fallback

    def get_dashboard_interval(self) -> str:
        """Get dashboard data interval"""
        return os.getenv("BINANCE_DASHBOARD_INTERVAL", "1m")

    def should_enable_bots(self) -> bool:
        """
        Determine if bot orchestrator should be enabled.

        Returns:
            True if bots should be enabled for current pipeline
        """
        return os.getenv("BINANCE_ENABLE_BOTS", "false").lower() == "true"

    def should_enable_market_data(self) -> bool:
        """
        Determine if market data streaming should be enabled.

        Returns:
            True if market data should be enabled
        """
        return os.getenv("BINANCE_ENABLE_MARKET_DATA", "true").lower() == "true"

    def validate_pipeline_config(self) -> tuple[bool, list[str]]:
        """
        Validate all configurations for the current pipeline.

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []

        # Validate Binance config
        binance_config = self.get_binance_config()
        if binance_config:
            valid, error = binance_config.validate()
            if not valid:
                errors.append(f"Binance config: {error}")

        # Validate Redis config (optional - just validates if enabled)
        redis_config = self.get_redis_config()
        valid, error = redis_config.validate()
        if not valid:
            errors.append(f"Redis config: {error}")

        # Validate Database config (optional - application continues without it)
        db_config = self.get_database_config()
        valid, error = db_config.validate()
        # Database is optional now, so we don't add to errors
        # if not valid:
        #     errors.append(f"Database config: {error}")

        return len(errors) == 0, errors

    def get_service_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all service configurations.

        Returns:
            Dictionary containing service config summary
        """
        summary = {
            "pipeline": self.pipeline.value,
            "services": {},
        }

        # Binance services
        if self.pipeline in [Pipeline.BINANCE_PAPER, Pipeline.BINANCE_LIVE]:
            binance_config = self.get_binance_config()
            if binance_config:
                summary["services"]["binance"] = {
                    "enabled": True,
                    "testnet": binance_config.testnet,
                    "test_mode": binance_config.test_mode,
                    "base_url": binance_config.base_url,
                    "has_credentials": bool(binance_config.api_key and binance_config.api_secret),
                }

        # Redis
        redis_config = self.get_redis_config()
        summary["services"]["redis"] = {
            "enabled": redis_config.enabled,
            "host": redis_config.host or "disabled",
            "port": redis_config.port,
            "db": redis_config.db,
            "has_password": bool(redis_config.password),
        }

        # Database
        db_config = self.get_database_config()
        summary["services"]["database"] = {
            "enabled": True,
            "has_url": bool(db_config.url),
            "pool_size": db_config.pool_size,
        }

        # Bot orchestrator
        summary["services"]["bot_orchestrator"] = {
            "enabled": self.should_enable_bots(),
        }

        # Market data
        summary["services"]["market_data"] = {
            "enabled": self.should_enable_market_data(),
            "symbols": self.get_dashboard_symbols(),
            "interval": self.get_dashboard_interval(),
        }

        return summary


def get_pipeline_config(pipeline: Optional[Pipeline] = None) -> PipelineServiceConfig:
    """
    Factory function to get pipeline-specific configuration.

    Args:
        pipeline: Optional pipeline to configure for. Uses current if not specified.

    Returns:
        PipelineServiceConfig instance
    """
    return PipelineServiceConfig(pipeline)
