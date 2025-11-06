from __future__ import annotations

import enum
import os
from pathlib import Path
from typing import List


class Pipeline(str, enum.Enum):
    BINANCE_PAPER = "binance_paper"
    BINANCE_LIVE = "binance_live"


DEFAULT_PIPELINE = Pipeline.BINANCE_PAPER
PIPELINE_ENV_KEY = "CURRENT_PIPELINE"
PIPELINE_STATE_FILE = Path("pipeline_state.txt")


def get_available_pipelines() -> List[Pipeline]:
    return [Pipeline.BINANCE_PAPER, Pipeline.BINANCE_LIVE]


def _read_persistent_pipeline() -> str | None:
    if PIPELINE_STATE_FILE.exists():
        try:
            return PIPELINE_STATE_FILE.read_text().strip()
        except OSError:
            return None
    return None


def _write_persistent_pipeline(value: str) -> None:
    try:
        PIPELINE_STATE_FILE.write_text(value)
    except OSError:
        pass


def get_current_pipeline() -> Pipeline:
    raw = os.getenv(PIPELINE_ENV_KEY)
    if not raw:
        raw = _read_persistent_pipeline()
    if not raw:
        return DEFAULT_PIPELINE
    try:
        return Pipeline(raw)
    except ValueError:
        return DEFAULT_PIPELINE


def set_current_pipeline(pipeline: Pipeline) -> None:
    os.environ[PIPELINE_ENV_KEY] = pipeline.value
    _write_persistent_pipeline(pipeline.value)


def is_binance_paper() -> bool:
    return get_current_pipeline() == Pipeline.BINANCE_PAPER


def fixtures_enabled() -> bool:
    enable_fixtures = os.getenv("ENABLE_DASHBOARD_FIXTURES", "true").lower() == "true"
    return enable_fixtures and is_binance_paper()
