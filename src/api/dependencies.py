from __future__ import annotations

from typing import Dict

from .pipeline import Pipeline, get_current_pipeline, get_available_pipelines, set_current_pipeline

PIPELINE_LABELS = {
    Pipeline.BINANCE_PAPER: "Binance Paper",
    Pipeline.BINANCE_LIVE: "Binance Live",
}


def get_pipeline_metadata() -> Dict[str, str]:
    pipeline = get_current_pipeline()
    return {
        "current": pipeline.value,
        "label": PIPELINE_LABELS[pipeline],
    }


def list_pipeline_options():
    options = []
    for pipeline in get_available_pipelines():
        options.append({
            "id": pipeline.value,
            "label": PIPELINE_LABELS[pipeline],
        })
    return options


def select_pipeline(pipeline_id: str) -> Dict[str, str]:
    try:
        pipeline = Pipeline(pipeline_id)
    except ValueError:
        raise ValueError("Invalid pipeline")

    set_current_pipeline(pipeline)
    return {
        "current": pipeline.value,
        "label": PIPELINE_LABELS[pipeline],
    }
