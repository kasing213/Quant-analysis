"""
Utility script to exercise pipeline switching in the Binance-only environment.

Usage:
    python scripts/test_pipeline_switching.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.pipeline import Pipeline, set_current_pipeline, get_current_pipeline  # noqa: E402
from src.api.pipeline_config import get_pipeline_config  # noqa: E402


def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"{title}")
    print("=" * 70)


def describe_pipeline(pipeline: Pipeline) -> None:
    config = get_pipeline_config(pipeline)
    binance = config.get_binance_config()
    redis_cfg = config.get_redis_config()

    print(f"\nPipeline: {pipeline.value}")
    print(f"  Binance testnet: {binance.testnet}")
    print(f"  Binance test mode: {binance.test_mode}")
    print(f"  Binance REST URL: {binance.base_url}")
    print(f"  Binance WS URL: {binance.ws_base_url}")
    print(f"  Redis DB: {redis_cfg.db}")
    print(f"  Dashboard symbols: {', '.join(config.get_dashboard_symbols())}")
    print(f"  Dashboard interval: {config.get_dashboard_interval()}")
    print(f"  Bots enabled: {config.should_enable_bots()}")
    print(f"  Market data enabled: {config.should_enable_market_data()}")

    valid, errors = config.validate_pipeline_config()
    status = "VALID" if valid else "INVALID"
    print(f"  Validation: {status}")
    if errors:
        for error in errors:
            print(f"    - {error}")

    summary = config.get_service_summary()
    print("  Service summary:")
    print(json.dumps(summary, indent=2))


async def main() -> None:
    print_header("PIPELINE SWITCHING DIAGNOSTICS")

    for pipeline in [Pipeline.BINANCE_PAPER, Pipeline.BINANCE_LIVE]:
        print_header(f"Testing pipeline: {pipeline.value}")
        set_current_pipeline(pipeline)
        print(f"Current pipeline set to: {get_current_pipeline().value}")
        describe_pipeline(pipeline)

    print_header("Pipeline persistence check")
    original = get_current_pipeline()
    try:
        set_current_pipeline(Pipeline.BINANCE_LIVE)
        assert get_current_pipeline() == Pipeline.BINANCE_LIVE
        set_current_pipeline(Pipeline.BINANCE_PAPER)
        assert get_current_pipeline() == Pipeline.BINANCE_PAPER
        print("Persistence check passed.")
    finally:
        set_current_pipeline(original)

    print_header("Diagnostics complete")


if __name__ == "__main__":
    asyncio.run(main())
