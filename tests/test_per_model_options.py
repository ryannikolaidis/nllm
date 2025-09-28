"""Tests for per-model options functionality."""

import pytest

from nllm.config import parse_cli_model_options, resolve_models
from nllm.models import ModelConfig, NllmConfig
from nllm.utils import ConfigError


class TestPerModelOptions:
    """Test per-model options functionality."""

    def test_parse_cli_model_options(self):
        """Test parsing CLI model options."""
        options = ["gpt-4:-o:temperature:0.7", "claude-3-sonnet:--system:Be concise"]
        result = parse_cli_model_options(options)

        expected = {
            "gpt-4": ["-o", "temperature", "0.7"],
            "claude-3-sonnet": ["--system", "Be concise"]
        }
        assert result == expected

    def test_parse_cli_model_options_multiple_for_same_model(self):
        """Test parsing multiple CLI model options for the same model."""
        options = ["gpt-4:-o:temperature:0.7", "gpt-4:--system:Be helpful"]
        result = parse_cli_model_options(options)

        expected = {
            "gpt-4": ["-o", "temperature", "0.7", "--system", "Be helpful"]
        }
        assert result == expected

    def test_parse_cli_model_options_invalid_format(self):
        """Test parsing CLI model options with invalid format."""
        with pytest.raises(ConfigError, match="Invalid model option format"):
            parse_cli_model_options(["invalid-format"])

    def test_resolve_models_cli_only(self):
        """Test resolving models from CLI only."""
        config = NllmConfig()
        result = resolve_models(["gpt-4", "claude-3-sonnet"], [], config)

        expected = [
            ModelConfig(name="gpt-4", options=[]),
            ModelConfig(name="claude-3-sonnet", options=[])
        ]
        assert result == expected

    def test_resolve_models_cli_with_options(self):
        """Test resolving models from CLI with options."""
        config = NllmConfig()
        cli_options = ["gpt-4:-o:temperature:0.7", "claude-3-sonnet:--system:Be concise"]
        result = resolve_models(["gpt-4", "claude-3-sonnet"], cli_options, config)

        expected = [
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.7"]),
            ModelConfig(name="claude-3-sonnet", options=["--system", "Be concise"])
        ]
        assert result == expected

    def test_resolve_models_config_only(self):
        """Test resolving models from config only."""
        config = NllmConfig(models=[
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.5"]),
            ModelConfig(name="claude-3-sonnet", options=[])
        ])
        result = resolve_models(None, [], config)

        expected = [
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.5"]),
            ModelConfig(name="claude-3-sonnet", options=[])
        ]
        assert result == expected

    def test_resolve_models_config_with_cli_options_merge(self):
        """Test resolving models from config with CLI options merged."""
        config = NllmConfig(models=[
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.5"]),
        ])
        cli_options = ["gpt-4:--system:Be helpful"]
        result = resolve_models(None, cli_options, config)

        expected = [
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.5", "--system", "Be helpful"])
        ]
        assert result == expected

    def test_resolve_models_cli_options_only(self):
        """Test resolving models from CLI options only (no CLI models or config)."""
        config = NllmConfig()
        cli_options = ["gpt-4:-o:temperature:0.7"]
        result = resolve_models(None, cli_options, config)

        expected = [
            ModelConfig(name="gpt-4", options=["-o", "temperature", "0.7"])
        ]
        assert result == expected

    def test_model_config_from_string(self):
        """Test creating ModelConfig from string."""
        result = ModelConfig.from_string("gpt-4")
        expected = ModelConfig(name="gpt-4", options=[])
        assert result == expected

    def test_model_config_from_dict(self):
        """Test creating ModelConfig from dict."""
        data = {"name": "gpt-4", "options": ["-o", "temperature", "0.7"]}
        result = ModelConfig.from_dict(data)
        expected = ModelConfig(name="gpt-4", options=["-o", "temperature", "0.7"])
        assert result == expected

    def test_model_config_from_dict_no_name(self):
        """Test creating ModelConfig from dict without name."""
        data = {"options": ["-o", "temperature", "0.7"]}
        with pytest.raises(ValueError, match="Model config must have 'name' field"):
            ModelConfig.from_dict(data)

    def test_nllm_config_from_dict_mixed_models(self):
        """Test creating NllmConfig from dict with mixed model formats."""
        data = {
            "models": [
                "gpt-4",  # String format
                {"name": "claude-3-sonnet", "options": ["-o", "temperature", "0.2"]}  # Dict format
            ]
        }
        result = NllmConfig.from_dict(data)

        expected_models = [
            ModelConfig(name="gpt-4", options=[]),
            ModelConfig(name="claude-3-sonnet", options=["-o", "temperature", "0.2"])
        ]
        assert result.models == expected_models

    def test_nllm_config_get_model_names(self):
        """Test getting model names from NllmConfig."""
        config = NllmConfig(models=[
            ModelConfig(name="gpt-4", options=[]),
            ModelConfig(name="claude-3-sonnet", options=["-o", "temperature", "0.2"])
        ])
        result = config.get_model_names()
        expected = ["gpt-4", "claude-3-sonnet"]
        assert result == expected

    def test_nllm_config_get_model_config(self):
        """Test getting specific model config from NllmConfig."""
        model_config = ModelConfig(name="gpt-4", options=["-o", "temperature", "0.7"])
        config = NllmConfig(models=[model_config])

        result = config.get_model_config("gpt-4")
        assert result == model_config

        result = config.get_model_config("nonexistent")
        assert result is None