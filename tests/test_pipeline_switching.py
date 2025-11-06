"""
Automated tests for pipeline switching functionality in the Binance-only setup.

Focus areas:
1. Pipeline configuration detection
2. Credential switching between paper/live
3. Service configuration validation
4. Redis database isolation
5. Symbol configuration
6. Pipeline state persistence
"""

import os
from pathlib import Path

import pytest

from src.api.pipeline import (
    Pipeline,
    set_current_pipeline,
    get_current_pipeline,
    get_available_pipelines,
    is_binance_paper,
    DEFAULT_PIPELINE,
    PIPELINE_STATE_FILE,
)
from src.api.pipeline_config import get_pipeline_config


class TestPipelineBasics:
    """Test basic pipeline functionality."""

    def test_get_available_pipelines(self):
        """Only Binance paper/live pipelines should be exposed."""
        pipelines = get_available_pipelines()
        assert pipelines == [Pipeline.BINANCE_PAPER, Pipeline.BINANCE_LIVE]

    def test_default_pipeline(self):
        """Default pipeline remains Binance paper."""
        assert DEFAULT_PIPELINE == Pipeline.BINANCE_PAPER

    def test_is_binance_paper(self):
        """Ensure helper flag reflects current pipeline."""
        set_current_pipeline(Pipeline.BINANCE_PAPER)
        assert is_binance_paper() is True

        set_current_pipeline(Pipeline.BINANCE_LIVE)
        assert is_binance_paper() is False


class TestPipelinePersistence:
    """Test pipeline state persistence."""

    def setup_method(self):
        """Clean up before each test."""
        if PIPELINE_STATE_FILE.exists():
            PIPELINE_STATE_FILE.unlink()
        os.environ.pop("CURRENT_PIPELINE", None)

    def teardown_method(self):
        """Clean up after each test."""
        if PIPELINE_STATE_FILE.exists():
            PIPELINE_STATE_FILE.unlink()
        os.environ.pop("CURRENT_PIPELINE", None)

    def test_set_and_get_pipeline(self):
        """Setting a pipeline should be reflected immediately."""
        set_current_pipeline(Pipeline.BINANCE_LIVE)
        assert get_current_pipeline() == Pipeline.BINANCE_LIVE

        set_current_pipeline(Pipeline.BINANCE_PAPER)
        assert get_current_pipeline() == Pipeline.BINANCE_PAPER

    def test_pipeline_persists_to_file(self):
        """Pipeline selection is persisted to disk."""
        set_current_pipeline(Pipeline.BINANCE_LIVE)
        assert PIPELINE_STATE_FILE.exists()
        assert PIPELINE_STATE_FILE.read_text().strip() == Pipeline.BINANCE_LIVE.value

    def test_pipeline_reads_from_file(self):
        """Fallback to persisted file when env var not present."""
        PIPELINE_STATE_FILE.write_text(Pipeline.BINANCE_LIVE.value)
        os.environ.pop("CURRENT_PIPELINE", None)
        assert get_current_pipeline() == Pipeline.BINANCE_LIVE

    def test_environment_overrides_file(self):
        """Environment variable takes precedence over disk state."""
        PIPELINE_STATE_FILE.write_text(Pipeline.BINANCE_LIVE.value)
        os.environ["CURRENT_PIPELINE"] = Pipeline.BINANCE_PAPER.value
        assert get_current_pipeline() == Pipeline.BINANCE_PAPER

    def test_invalid_pipeline_falls_back_to_default(self):
        """Invalid persisted state should fall back safely."""
        PIPELINE_STATE_FILE.write_text("invalid_pipeline")
        os.environ.pop("CURRENT_PIPELINE", None)
        assert get_current_pipeline() == DEFAULT_PIPELINE


class TestPipelineConfigurations:
    """Test pipeline-specific configurations."""

    def test_binance_paper_configuration(self):
        """Paper mode should use testnet settings."""
        config = get_pipeline_config(Pipeline.BINANCE_PAPER)
        assert config.pipeline == Pipeline.BINANCE_PAPER

        binance_config = config.get_binance_config()
        assert binance_config is not None
        assert binance_config.testnet is True
        assert binance_config.test_mode is True
        assert "testnet" in binance_config.base_url.lower()

    def test_binance_live_configuration(self):
        """Live mode should target production endpoints."""
        config = get_pipeline_config(Pipeline.BINANCE_LIVE)
        assert config.pipeline == Pipeline.BINANCE_LIVE

        binance_config = config.get_binance_config()
        assert binance_config is not None
        assert binance_config.testnet is False
        assert isinstance(binance_config.test_mode, bool)

    def test_all_pipelines_load_successfully(self):
        """Every pipeline should produce a valid config object."""
        for pipeline in get_available_pipelines():
            config = get_pipeline_config(pipeline)
            assert config is not None
            assert config.pipeline == pipeline


class TestCredentialIsolation:
    """Test that credentials are properly isolated per pipeline."""

    def test_binance_pipelines_have_distinct_settings(self):
        """Paper/live credentials should not be identical."""
        paper_config = get_pipeline_config(Pipeline.BINANCE_PAPER)
        live_config = get_pipeline_config(Pipeline.BINANCE_LIVE)

        paper_binance = paper_config.get_binance_config()
        live_binance = live_config.get_binance_config()

        assert paper_binance is not None
        assert live_binance is not None
        assert paper_binance.testnet is True
        assert live_binance.testnet is False
        assert paper_binance.base_url != live_binance.base_url


class TestRedisDatabaseIsolation:
    """Test that different pipelines use different Redis databases."""

    def test_each_pipeline_uses_unique_redis_db(self):
        """Paper and live pipelines should isolate Redis databases."""
        db_numbers = {
            pipeline: get_pipeline_config(pipeline).get_redis_config().db
            for pipeline in get_available_pipelines()
        }
        assert len(set(db_numbers.values())) == len(db_numbers)

    def test_expected_redis_db_assignments(self):
        """Confirm the explicit DB numbers remain stable."""
        assert get_pipeline_config(Pipeline.BINANCE_PAPER).get_redis_config().db == 0
        assert get_pipeline_config(Pipeline.BINANCE_LIVE).get_redis_config().db == 1


class TestSymbolSelection:
    """Test that symbols are selected appropriately per pipeline."""

    def test_binance_pipelines_use_crypto_symbols(self):
        """Default symbols should contain common crypto pairs."""
        crypto_indicators = ("USDT", "BTC", "ETH", "BNB")
        for pipeline in get_available_pipelines():
            symbols = get_pipeline_config(pipeline).get_dashboard_symbols()
            assert symbols, f"No symbols for {pipeline.value}"
            assert any(
                indicator in symbol
                for symbol in symbols
                for indicator in crypto_indicators
            ), f"No crypto symbols found for {pipeline.value}"

    def test_dashboard_interval_is_configurable(self):
        """Dashboard interval must be a non-empty string."""
        for pipeline in get_available_pipelines():
            interval = get_pipeline_config(pipeline).get_dashboard_interval()
            assert isinstance(interval, str) and interval.strip()


class TestServiceFlags:
    """Test service enable/disable flags per pipeline."""

    def test_bots_and_market_data_flags_are_boolean(self):
        """Flag helpers should always return booleans."""
        for pipeline in get_available_pipelines():
            config = get_pipeline_config(pipeline)
            assert isinstance(config.should_enable_bots(), bool)
            assert isinstance(config.should_enable_market_data(), bool)


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_all_pipeline_configs_are_valid(self):
        """Validation should return a boolean and list of errors."""
        for pipeline in get_available_pipelines():
            config = get_pipeline_config(pipeline)
            is_valid, errors = config.validate_pipeline_config()
            assert isinstance(is_valid, bool)
            assert isinstance(errors, list)

    def test_service_summary_returns_expected_shape(self):
        """Service summary should include key sections."""
        for pipeline in get_available_pipelines():
            summary = get_pipeline_config(pipeline).get_service_summary()
            assert summary["pipeline"] == pipeline.value
            assert "services" in summary
            assert "redis" in summary["services"]
            assert "database" in summary["services"]


class TestPipelineSwitching:
    """Test switching between pipelines."""

    def setup_method(self):
        self.original_pipeline = get_current_pipeline()

    def teardown_method(self):
        set_current_pipeline(self.original_pipeline)
        if PIPELINE_STATE_FILE.exists():
            PIPELINE_STATE_FILE.unlink()

    def test_switch_between_pipelines(self):
        """Switching should persist selected pipeline."""
        set_current_pipeline(Pipeline.BINANCE_PAPER)
        assert get_current_pipeline() == Pipeline.BINANCE_PAPER

        set_current_pipeline(Pipeline.BINANCE_LIVE)
        assert get_current_pipeline() == Pipeline.BINANCE_LIVE

        set_current_pipeline(Pipeline.BINANCE_PAPER)
        assert get_current_pipeline() == Pipeline.BINANCE_PAPER


# Integration tests (require environment setup)
@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests for pipeline switching."""

    @pytest.mark.asyncio
    async def test_pipeline_switch_with_services(self):
        """Placeholder for service-level integration coverage."""
        pass

    @pytest.mark.asyncio
    async def test_redis_isolation_with_real_redis(self, real_redis):
        """Placeholder for Redis isolation integration coverage."""
        pass
