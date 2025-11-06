# This is the new pipeline-aware lifespan function to replace the one in main.py (lines 45-198)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager with pipeline-aware service initialization.

    Services are configured based on the current pipeline mode:
    - BINANCE_PAPER: Testnet credentials, test mode enabled
    - BINANCE_LIVE: Production credentials, live trading
    """
    logger.info("Starting up Portfolio Management API...")

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

        # Initialize database connections
        await init_db()
        logger.info("Database initialization completed")

        # Test database connectivity
        db_status = await test_db_connection()
        if db_status["status"] != "healthy":
            logger.error(f"Database health check failed: {db_status}")
            raise Exception("Database connection failed during startup")

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
                        logger.info(
                            f"Binance bot orchestrator initialized "
                            f"(testnet={binance_config.testnet}, test_mode={binance_config.test_mode})"
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
                    logger.info("Binance bot orchestrator initialized in TEST MODE (simulated executions)")

            except Exception as orchestrator_error:
                bot_orchestrator = None
                bots.set_orchestrator(None)
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
