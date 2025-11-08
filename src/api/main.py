from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import time
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import random

from .database import (
    init_db,
    close_db_connections,
    test_db_connection,
    get_db_info,
    get_async_db
)
from .routers import portfolio, trades, positions, backtesting, bots, pipeline as pipeline_router
from .pipeline_config import get_pipeline_config
from src.binance import BotOrchestrator, BinanceDataManager

# Initialize logging first before any other imports that might need it
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
try:
    from prometheus_client import make_asgi_app
    from prometheus_fastapi_instrumentator import Instrumentator
    from .metrics import (
        initialize_metrics,
        WEBSOCKET_CONNECTIONS,
        MARKET_DATA_UPDATES,
        record_market_data_update,
        update_websocket_subscribers,
        record_websocket_message,
        record_websocket_broadcast
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available, metrics disabled")

# Application startup time for uptime calculation
startup_time = time.time()

# Global bot orchestrator instance (optional)
bot_orchestrator: Optional[BotOrchestrator] = None

# Shared Binance data manager for dashboard endpoints
binance_data_manager: Optional[BinanceDataManager] = None
binance_stream_task: Optional[asyncio.Task] = None
binance_data_manager_owned = False  # Track whether this module created the manager
dashboard_symbols: List[str] = []
dashboard_interval: str = "1m"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager with pipeline-aware service initialization.

    Services are configured based on the current pipeline mode:
    - BINANCE_PAPER: Testnet credentials, test mode enabled
    - BINANCE_LIVE: Production credentials, live trading
    """
    logger.info("Starting up Portfolio Management API...")

    # Initialize Prometheus metrics if available
    if PROMETHEUS_AVAILABLE:
        initialize_metrics()
        logger.info("Prometheus metrics initialized")

    try:
        global bot_orchestrator, binance_data_manager, binance_stream_task
        global binance_data_manager_owned, dashboard_symbols, dashboard_interval

        # Get pipeline-specific configuration
        pipeline_config = get_pipeline_config()
        logger.info(f"Using pipeline configuration: {pipeline_config.pipeline.value}")

        # Validate pipeline configuration
        is_valid, errors = pipeline_config.validate_pipeline_config()
        if not is_valid:
            logger.error(f"Pipeline configuration validation failed: {errors}")
            # Log warnings but continue - some services may work without credentials
            for error in errors:
                logger.warning(f"  - {error}")

        # Log service configuration summary
        service_summary = pipeline_config.get_service_summary()
        logger.info(f"Service configuration: {json.dumps(service_summary, indent=2)}")

        # Initialize database connections (optional - continue without DB if unavailable)
        try:
            await init_db()
            logger.info("Database initialization completed")

            # Test database connectivity
            db_status = await test_db_connection()
            if db_status["status"] == "healthy":
                logger.info("Database connection healthy")
            else:
                logger.warning(f"Database health check failed: {db_status}")
                logger.warning("Continuing without database - some features may be limited")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            logger.warning("Continuing without database - API will run in limited mode")

        logger.info("Portfolio API startup completed successfully")

        # Initialize Binance services if applicable to current pipeline
        binance_config = pipeline_config.get_binance_config()
        if binance_config and pipeline_config.should_enable_bots():
            try:
                # Get Redis configuration
                redis_config = pipeline_config.get_redis_config()

                # Validate credentials for non-test mode
                if not binance_config.test_mode:
                    valid, error = binance_config.validate()
                    if not valid:
                        logger.error(f"Binance configuration invalid: {error}")
                        logger.warning("Bot orchestrator will not be initialized")
                        bot_orchestrator = None
                    else:
                        # Initialize with pipeline-specific credentials
                        bot_orchestrator = BotOrchestrator(
                            api_key=binance_config.api_key,
                            api_secret=binance_config.api_secret,
                            redis_host=redis_config.host,
                            redis_port=redis_config.port,
                            testnet=binance_config.testnet,
                            test_mode=binance_config.test_mode
                        )
                        await bot_orchestrator.initialize()
                        bots.set_orchestrator(bot_orchestrator)
                        # Pass persistence instance to bots router
                        if bot_orchestrator.persistence:
                            bots.set_persistence(bot_orchestrator.persistence)
                        # Pass orchestrator to portfolio router for live data
                        portfolio.set_bot_orchestrator(bot_orchestrator)
                        logger.info(
                            f"Binance bot orchestrator initialized "
                            f"(testnet={binance_config.testnet}, test_mode={binance_config.test_mode}, "
                            f"persistence={'enabled' if bot_orchestrator.persistence else 'disabled'})"
                        )
                else:
                    # Test mode - initialize with test credentials
                    bot_orchestrator = BotOrchestrator(
                        api_key=binance_config.api_key or "",
                        api_secret=binance_config.api_secret or "",
                        redis_host=redis_config.host,
                        redis_port=redis_config.port,
                        testnet=binance_config.testnet,
                        test_mode=True
                    )
                    await bot_orchestrator.initialize()
                    bots.set_orchestrator(bot_orchestrator)
                    # Pass persistence instance to bots router
                    if bot_orchestrator.persistence:
                        bots.set_persistence(bot_orchestrator.persistence)
                    # Pass orchestrator to portfolio router for live data
                    portfolio.set_bot_orchestrator(bot_orchestrator)
                    logger.info(
                        "Binance bot orchestrator initialized in TEST MODE (simulated executions), "
                        f"persistence={'enabled' if bot_orchestrator.persistence else 'disabled'}"
                    )

            except Exception as orchestrator_error:
                bot_orchestrator = None
                bots.set_orchestrator(None)
                bots.set_persistence(None)
                logger.error(f"Failed to initialize bot orchestrator: {orchestrator_error}")

        else:
            bots.set_orchestrator(None)
            if binance_config:
                logger.info("Binance bot orchestrator disabled (BINANCE_ENABLE_BOTS != 'true')")
            else:
                logger.info(f"Binance services not available for pipeline: {pipeline_config.pipeline.value}")

        # Initialize market data manager for dashboard
        if binance_config and pipeline_config.should_enable_market_data():
            # Get pipeline-specific symbols and interval
            dashboard_symbols = pipeline_config.get_dashboard_symbols()
            dashboard_interval = pipeline_config.get_dashboard_interval()
            logger.info(f"Dashboard symbols: {dashboard_symbols}, interval: {dashboard_interval}")

            try:
                if bot_orchestrator:
                    # Reuse orchestrator-managed data manager
                    binance_data_manager = bot_orchestrator.data_manager
                    await binance_data_manager.subscribe_multiple_symbols(
                        dashboard_symbols,
                        interval=dashboard_interval
                    )
                    logger.info(
                        "Dashboard market data using orchestrator-managed BinanceDataManager "
                        f"for symbols: {', '.join(dashboard_symbols)}"
                    )
                else:
                    # Create standalone data manager
                    redis_config = pipeline_config.get_redis_config()
                    redis_password = redis_config.password

                    binance_data_manager = BinanceDataManager(
                        redis_host=redis_config.host,
                        redis_port=redis_config.port,
                        redis_password=redis_password,
                        testnet=binance_config.testnet
                    )
                    await binance_data_manager.connect()
                    await binance_data_manager.subscribe_multiple_symbols(
                        dashboard_symbols,
                        interval=dashboard_interval
                    )
                    binance_stream_task = asyncio.create_task(
                        binance_data_manager.start_streaming()
                    )
                    binance_data_manager_owned = True
                    logger.info(
                        "Dashboard market data streaming started for symbols: "
                        f"{', '.join(dashboard_symbols)}"
                    )

            except Exception as data_error:
                logger.error(f"Failed to initialize Binance market data manager: {data_error}")
                binance_data_manager = None
                binance_stream_task = None
                binance_data_manager_owned = False

        else:
            logger.info(
                f"Market data manager disabled for pipeline: {pipeline_config.pipeline.value}"
            )

        logger.info(f"Pipeline {pipeline_config.pipeline.value} services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to start Portfolio API: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Portfolio API...")
    try:
        if bot_orchestrator:
            await bot_orchestrator.shutdown()
            logger.info("Bot orchestrator shut down")

        if binance_stream_task and not binance_stream_task.done():
            binance_stream_task.cancel()
            try:
                await binance_stream_task
            except asyncio.CancelledError:
                pass

        if binance_data_manager and binance_data_manager_owned:
            await binance_data_manager.close()
            logger.info("Binance data manager closed")

        await close_db_connections()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    logger.info("Portfolio API shutdown completed")

app = FastAPI(
    title="Quantitative Trading Portfolio API",
    description="""
    Professional quantitative trading portfolio management system with PostgreSQL integration.

    Features:
    - Real-time portfolio tracking
    - Trade execution and management
    - Position monitoring
    - Risk analytics
    - Database health monitoring
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Prometheus metrics instrumentation
if PROMETHEUS_AVAILABLE:
    # Instrument FastAPI with Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus instrumentation enabled on /metrics endpoint")

# Enhanced CORS configuration for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"]
)

# Include API routers
app.include_router(pipeline_router.router, prefix="/api/v1", tags=["Pipelines"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["Portfolio"])
app.include_router(trades.router, prefix="/api/v1", tags=["Trades"])
app.include_router(positions.router, prefix="/api/v1", tags=["Positions"])
app.include_router(backtesting.router, tags=["Backtesting"])
app.include_router(bots.router, prefix="/api/v1")

@app.get("/system/info", tags=["System"])
async def system_info():
    """API system information endpoint"""
    uptime_seconds = time.time() - startup_time
    return {
        "service": "Quantitative Trading Portfolio API",
        "version": "2.0.0",
        "status": "operational",
        "uptime_seconds": round(uptime_seconds, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_data": {
            "source": "binance" if binance_data_manager else "unavailable",
            "enabled": binance_data_manager is not None,
            "symbols_count": len(dashboard_symbols) if dashboard_symbols else 0
        },
        "endpoints": {
            "health": "/health",
            "database": "/health/database",
            "market_data_health": "/health/market-data",
            "detailed": "/health/detailed",
            "api_docs": "/docs",
            "portfolio": "/api/v1/portfolio",
            "trades": "/api/v1/trades",
            "positions": "/api/v1/positions",
            "market_symbols": "/api/v1/market/symbols",
            "market_quotes": "/api/v1/market/quotes"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "portfolio-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - startup_time, 2)
    }

@app.get("/health/database", tags=["Health"])
async def database_health():
    """Database-specific health check"""
    db_status = await test_db_connection()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "overall_status": db_status["status"]
    }

@app.get("/health/detailed", tags=["Health"])
async def detailed_health():
    """Comprehensive health check with detailed system information"""
    try:
        # Test database connectivity
        db_status = await test_db_connection()
        db_info = await get_db_info()

        uptime_seconds = time.time() - startup_time

        # Check market data health
        market_data_status = "healthy"
        market_data_info = {}

        if binance_data_manager:
            try:
                market_health = await binance_data_manager.health_check()
                if not market_health.get('redis', False):
                    market_data_status = "degraded"
                elif not market_health.get('websocket', False):
                    market_data_status = "degraded"
                market_data_info = market_health
            except Exception:
                market_data_status = "unhealthy"
        else:
            market_data_status = "unavailable"

        health_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "portfolio-api",
            "version": "2.0.0",
            "uptime_seconds": round(uptime_seconds, 2),
            "status": "healthy" if db_status["status"] == "healthy" and market_data_status in ["healthy", "unavailable"] else "degraded",
            "components": {
                "database": {
                    "status": db_status["status"],
                    "connections": db_status,
                    "info": db_info.get("database_info", {}),
                    "pool": db_info.get("connection_pool", {})
                },
                "market_data": {
                    "status": market_data_status,
                    "info": market_data_info,
                    "symbols_count": len(dashboard_symbols) if dashboard_symbols else 0
                },
                "api": {
                    "status": "healthy",
                    "uptime": round(uptime_seconds, 2)
                }
            },
            "dependencies": {
                "postgresql": db_status["postgresql_manager"],
                "sqlalchemy": db_status["sqlalchemy_async"],
                "binance_data_manager": binance_data_manager is not None,
                "redis": market_data_info.get('redis', False) if market_data_info else False
            }
        }

        # Set overall status based on critical components
        if not db_status["postgresql_manager"] or not db_status["sqlalchemy_async"]:
            health_data["status"] = "unhealthy"

        return health_data

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unhealthy",
            "error": str(e),
            "service": "portfolio-api"
        }

@app.get("/health/database/info", tags=["Health"])
async def database_info():
    """Detailed database configuration and performance information"""
    try:
        info = await get_db_info()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **info
        }
    except Exception as e:
        logger.error(f"Database info retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database info error: {str(e)}")

@app.get("/health/market-data", tags=["Health"])
async def market_data_health():
    """Market data service health check"""
    try:
        global binance_data_manager, dashboard_symbols

        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "binance_manager_available": binance_data_manager is not None,
            "redis_healthy": False,
            "websocket_running": False,
            "active_symbols": [],
            "dashboard_symbols": dashboard_symbols or [],
            "status": "unhealthy"
        }

        if binance_data_manager:
            try:
                health = await binance_data_manager.health_check()
                health_status["redis_healthy"] = health.get('redis', False)
                health_status["websocket_running"] = health.get('websocket', False)
                health_status["active_symbols"] = health.get('active_symbols', [])

                if health_status["redis_healthy"] and health_status["websocket_running"]:
                    health_status["status"] = "healthy"
                elif health_status["redis_healthy"]:
                    health_status["status"] = "degraded"

            except Exception as exc:
                logger.error(f"Failed to get Binance manager health: {exc}")

        return health_status

    except Exception as e:
        logger.error(f"Market data health check failed: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e)
        }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "error": "Internal server error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": str(request.url)
    }

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        if PROMETHEUS_AVAILABLE:
            WEBSOCKET_CONNECTIONS.labels(endpoint="general").set(len(self.active_connections))
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Remove from all subscriptions
        for channel, subscribers in self.subscriptions.items():
            if websocket in subscribers:
                subscribers.remove(websocket)

        if PROMETHEUS_AVAILABLE:
            WEBSOCKET_CONNECTIONS.labels(endpoint="general").set(len(self.active_connections))
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        if websocket not in self.subscriptions[channel]:
            self.subscriptions[channel].append(websocket)

        # Update subscriber metrics
        if PROMETHEUS_AVAILABLE:
            update_websocket_subscribers(channel, len(self.subscriptions[channel]))

        logger.info(f"WebSocket subscribed to {channel}. Total subscribers: {len(self.subscriptions[channel])}")

    def unsubscribe(self, websocket: WebSocket, channel: str):
        if channel in self.subscriptions and websocket in self.subscriptions[channel]:
            self.subscriptions[channel].remove(websocket)

            # Update subscriber metrics
            if PROMETHEUS_AVAILABLE:
                update_websocket_subscribers(channel, len(self.subscriptions[channel]))

        logger.info(f"WebSocket unsubscribed from {channel}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast_to_channel(self, message: dict, channel: str):
        if channel in self.subscriptions:
            start_time = time.time()
            disconnected = []
            message_count = 0

            for websocket in self.subscriptions[channel]:
                try:
                    await websocket.send_text(json.dumps(message))
                    message_count += 1

                    # Record message sent
                    if PROMETHEUS_AVAILABLE:
                        record_websocket_message("sent", channel)

                except Exception as e:
                    logger.error(f"Failed to send message to websocket: {e}")
                    disconnected.append(websocket)

            # Remove disconnected websockets
            for ws in disconnected:
                self.disconnect(ws)

            # Record broadcast timing
            if PROMETHEUS_AVAILABLE and message_count > 0:
                duration = time.time() - start_time
                record_websocket_broadcast(channel, duration)
                logger.debug(f"Broadcast to {channel}: {message_count} messages in {duration:.4f}s")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                disconnected.append(connection)

        # Remove disconnected websockets
        for ws in disconnected:
            self.disconnect(ws)

manager = ConnectionManager()

# Legacy Market Data Generator (DEPRECATED - Replaced by BinanceMarketDataBroadcaster)
# This class is no longer used and can be removed once all integrations are confirmed working
# class MarketDataGenerator:
#     def __init__(self):
#         self.symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'SPY', 'QQQ']
#         self.prices = {symbol: 100 + random.random() * 900 for symbol in self.symbols}
#         self.is_running = False
#
#     async def start(self):
#         logger.warning("MarketDataGenerator is deprecated - use BinanceMarketDataBroadcaster instead")
#
#     def stop(self):
#         logger.info("MarketDataGenerator stopped (deprecated)")

# market_data_generator = MarketDataGenerator()  # DEPRECATED

# Binance Market Data Broadcaster
class BinanceMarketDataBroadcaster:
    """Broadcasts Binance real-time data from Redis to WebSocket clients"""

    def __init__(self):
        self.is_running = False
        self.broadcast_interval = 2  # seconds
        self.broadcast_task: Optional[asyncio.Task] = None
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.backoff_interval = 5  # seconds for backoff after errors

    def has_subscribers(self) -> bool:
        """Check if there are any active subscribers to market_data channel"""
        return len(manager.subscriptions.get('market_data', [])) > 0

    async def start(self):
        """Start broadcasting Binance market data"""
        if self.is_running and self.broadcast_task and not self.broadcast_task.done():
            logger.debug("Broadcaster already running")
            return

        global binance_data_manager, dashboard_symbols

        if not binance_data_manager or not dashboard_symbols:
            logger.warning("Binance data manager not available, cannot broadcast")
            return

        # Cancel existing task if it exists
        if self.broadcast_task and not self.broadcast_task.done():
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

        self.is_running = True
        self.consecutive_errors = 0
        logger.info(f"Starting Binance market data broadcaster for symbols: {dashboard_symbols}")

        # Start the broadcast loop as a task
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self):
        """Main broadcast loop with automatic stop when no subscribers"""
        global binance_data_manager, dashboard_symbols

        while self.is_running:
            try:
                # Check if there are any subscribers
                if not self.has_subscribers():
                    logger.info("No subscribers to market_data channel, stopping broadcaster")
                    self.stop()
                    break

                # Check Redis health before attempting to fetch data
                redis_healthy = await _check_redis_health()
                if not redis_healthy:
                    logger.warning("Redis connection unhealthy, waiting for recovery...")
                    self.consecutive_errors += 1

                    if self.consecutive_errors >= self.max_consecutive_errors:
                        logger.error(f"Redis unhealthy for {self.consecutive_errors} consecutive attempts, backing off")
                        await asyncio.sleep(self.backoff_interval)
                        self.consecutive_errors = 0  # Reset after backoff
                    else:
                        await asyncio.sleep(self.broadcast_interval)
                    continue

                # Fetch market data
                market_data = {}
                for symbol in dashboard_symbols:
                    quote = await _fetch_binance_quote(symbol)
                    if quote:
                        market_data[symbol] = quote
                        # Record metric for each market data update
                        if PROMETHEUS_AVAILABLE:
                            record_market_data_update(symbol, "websocket")

                if market_data:
                    # Broadcast to WebSocket subscribers
                    await manager.broadcast_to_channel({
                        'channel': 'market_data',
                        'type': 'price_update',
                        'payload': market_data,
                        'source': 'binance'
                    }, 'market_data')

                    # Reset error counter on successful broadcast
                    self.consecutive_errors = 0
                else:
                    logger.debug("No market data available to broadcast")

                await asyncio.sleep(self.broadcast_interval)

            except asyncio.CancelledError:
                logger.info("Broadcast loop cancelled")
                break
            except Exception as e:
                self.consecutive_errors += 1
                logger.error(f"Error in Binance market data broadcaster: {e}")

                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({self.consecutive_errors}), backing off")
                    await asyncio.sleep(self.backoff_interval)
                    self.consecutive_errors = 0
                else:
                    await asyncio.sleep(self.broadcast_interval)

        logger.info("Broadcast loop exited")

    def stop(self):
        """Stop broadcasting"""
        self.is_running = False
        if self.broadcast_task and not self.broadcast_task.done():
            self.broadcast_task.cancel()
        logger.info("Binance market data broadcaster stopped")

binance_broadcaster = BinanceMarketDataBroadcaster()

async def _check_redis_health() -> bool:
    """Check if Redis connection is healthy."""
    global binance_data_manager

    if not binance_data_manager:
        return False

    try:
        health = await binance_data_manager.health_check()
        return health.get('redis', False)
    except Exception as exc:
        logger.error(f"Redis health check failed: {exc}")
        return False

async def _fetch_binance_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch quote data from BinanceDataManager if available."""
    global binance_data_manager

    if not binance_data_manager:
        return None

    # Check Redis health first
    if not await _check_redis_health():
        logger.warning(f"Redis unhealthy, cannot fetch quote for {symbol}")
        return None

    try:
        # Ensure subscription for requested symbol
        await binance_data_manager.subscribe_symbol(symbol, interval=dashboard_interval)

        candles = await binance_data_manager.get_candles(
            symbol,
            interval=dashboard_interval,
            count=2
        )

        if candles.empty:
            return None

        latest = candles.iloc[-1]
        previous_close = candles.iloc[-2]["close"] if len(candles) > 1 else latest["close"]
        current_price = float(latest["close"])
        change = current_price - float(previous_close)
        change_percent = (change / previous_close) if previous_close else 0.0

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 4),
            "volume": float(latest.get("volume", 0.0)),
            "bid": round(current_price * 0.999, 2),
            "ask": round(current_price * 1.001, 2),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "source": "binance"
        }

    except Exception as exc:
        logger.error(f"Failed to fetch Binance quote for {symbol}: {exc}")
        return None


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get('type')
            channel = message.get('channel')

            if message_type == 'subscribe' and channel:
                manager.subscribe(websocket, channel)

                # Send confirmation
                await manager.send_personal_message({
                    'type': 'subscription_confirmed',
                    'channel': channel
                }, websocket)

                # Start market data broadcaster if subscribing to market data
                if channel == 'market_data':
                    # Prefer Binance data if available
                    if binance_data_manager and dashboard_symbols:
                        await binance_broadcaster.start()
                    else:
                        logger.warning("Binance data manager not available, market data unavailable")
                        await manager.send_personal_message({
                            'type': 'error',
                            'channel': channel,
                            'message': 'Market data unavailable - Binance integration required'
                        }, websocket)

            elif message_type == 'unsubscribe' and channel:
                manager.unsubscribe(websocket, channel)

                # Send confirmation
                await manager.send_personal_message({
                    'type': 'unsubscription_confirmed',
                    'channel': channel
                }, websocket)

                # Stop broadcaster if no more subscribers (will be checked in broadcast loop)
                if channel == 'market_data' and not binance_broadcaster.has_subscribers():
                    logger.info("Last client unsubscribed from market_data, broadcaster will stop")


            elif message_type == 'ping':
                await manager.send_personal_message({
                    'type': 'pong',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Market Data API Endpoints
@app.get("/api/v1/market/symbols", tags=["Market Data"])
async def get_available_symbols():
    """Get list of available symbols"""
    if binance_data_manager and dashboard_symbols:
        symbols = sorted(set(dashboard_symbols) | set(binance_data_manager.active_symbols))
        return {
            "symbols": symbols,
            "count": len(symbols),
            "source": "binance",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        raise HTTPException(
            status_code=503,
            detail="Market data service unavailable - Binance integration required"
        )

@app.get("/api/v1/market/quote/{symbol}", tags=["Market Data"])
async def get_quote(symbol: str):
    """Get current quote for a symbol"""
    symbol = symbol.upper()

    if binance_data_manager:
        quote = await _fetch_binance_quote(symbol)
        if quote:
            return quote
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol {symbol} not found or no data available"
            )
    else:
        raise HTTPException(
            status_code=503,
            detail="Market data service unavailable - Binance integration required"
        )

@app.get("/api/v1/market/quotes", tags=["Market Data"])
async def get_multiple_quotes(symbols: str = None):
    """Get quotes for multiple symbols"""
    if not binance_data_manager:
        raise HTTPException(
            status_code=503,
            detail="Market data service unavailable - Binance integration required"
        )

    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
    else:
        symbol_list = dashboard_symbols or []

    quotes = {}
    for symbol in symbol_list:
        quote = await _fetch_binance_quote(symbol)
        if quote:
            quotes[symbol] = quote

    return {
        "quotes": quotes,
        "count": len(quotes),
        "source": "binance",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/market/historical/{symbol}", tags=["Market Data"])
async def get_historical_data(
    symbol: str,
    period: str = "1M",
    interval: str = "1d"
):
    """Get historical data for a symbol"""
    symbol = symbol.upper()

    if not binance_data_manager:
        raise HTTPException(
            status_code=503,
            detail="Market data service unavailable - Binance integration required"
        )

    try:
        # Map period to count for Binance data
        periods_map = {
            "1D": 24, "1W": 168, "1M": 720, "3M": 2160, "6M": 4320, "1Y": 8760
        }
        count = periods_map.get(period, 720)  # Default to 1M

        await binance_data_manager.subscribe_symbol(symbol, interval=dashboard_interval)
        candles = await binance_data_manager.get_candles(
            symbol,
            interval=dashboard_interval,
            count=count
        )

        if candles.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data available for symbol {symbol}"
            )

        historical_data = [
            {
                "date": row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": round(float(row["open"]), 6),
                "high": round(float(row["high"]), 6),
                "low": round(float(row["low"]), 6),
                "close": round(float(row["close"]), 6),
                "volume": float(row["volume"]),
            }
            for _, row in candles.iterrows()
        ]

        return {
            "symbol": symbol,
            "period": period,
            "interval": dashboard_interval,
            "data": historical_data,
            "count": len(historical_data),
            "source": "binance"
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to fetch Binance historical data for {symbol}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch historical data for {symbol}: {str(exc)}"
        )

# Serve static files for the frontend (only if frontend directory exists)
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    logger.info(f"Frontend static files mounted from: {frontend_dir}")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}, static files not mounted")

@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the frontend dashboard"""
    from fastapi.responses import FileResponse

    frontend_index = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    if not frontend_index.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")

    return FileResponse(frontend_index)
