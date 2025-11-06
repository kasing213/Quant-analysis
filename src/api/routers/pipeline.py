from fastapi import APIRouter, HTTPException

from ..dependencies import (
    get_pipeline_metadata,
    list_pipeline_options,
    select_pipeline
)
from ..schemas import (
    PipelineStatus,
    PipelineDescriptor,
    PipelineSelectRequest,
    PipelineValidationResult,
    PipelineConfigSummary
)
from ..pipeline_config import get_pipeline_config

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("/", response_model=PipelineStatus)
async def get_pipeline_state():
    """Return the currently active pipeline alongside available options."""
    metadata = get_pipeline_metadata()
    options = list_pipeline_options()

    current = PipelineDescriptor(id=metadata["current"], label=metadata["label"])
    option_models = [PipelineDescriptor(**option) for option in options]

    return PipelineStatus(current=current, options=option_models)


@router.post("/select", response_model=PipelineDescriptor)
async def select_pipeline_endpoint(request: PipelineSelectRequest):
    """
    Activate a new pipeline configuration.

    Note: Server restart required for changes to take full effect.
    Use /pipelines/validate to check configuration before switching.
    """
    try:
        metadata = select_pipeline(request.pipeline_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return PipelineDescriptor(id=metadata["current"], label=metadata["label"])


@router.get("/validate", response_model=PipelineValidationResult)
async def validate_pipeline_config():
    """
    Validate the current pipeline configuration.

    Checks:
    - Credentials are properly configured
    - Required services are available
    - Configuration values are valid

    Returns validation status with detailed error messages if any issues found.
    """
    pipeline_config = get_pipeline_config()
    is_valid, errors = pipeline_config.validate_pipeline_config()
    summary = pipeline_config.get_service_summary()

    return PipelineValidationResult(
        pipeline=pipeline_config.pipeline.value,
        valid=is_valid,
        errors=errors,
        summary=summary
    )


@router.get("/config", response_model=PipelineConfigSummary)
async def get_pipeline_configuration():
    """
    Get detailed configuration information for the current pipeline.

    Returns:
    - Active pipeline mode
    - Service configuration details
    - Credential status (without exposing actual credentials)
    - Redis database assignment
    - Test/testnet mode status
    """
    pipeline_config = get_pipeline_config()
    summary = pipeline_config.get_service_summary()

    # Extract key configuration details
    binance_config = pipeline_config.get_binance_config()
    redis_config = pipeline_config.get_redis_config()

    # Determine if credentials are configured
    credentials_configured = False
    testnet_mode = None
    test_mode = None

    if binance_config:
        credentials_configured = bool(binance_config.api_key and binance_config.api_secret)
        testnet_mode = binance_config.testnet
        test_mode = binance_config.test_mode

    return PipelineConfigSummary(
        pipeline=pipeline_config.pipeline.value,
        services=summary["services"],
        credentials_configured=credentials_configured,
        redis_database=redis_config.db,
        testnet_mode=testnet_mode,
        test_mode=test_mode
    )
