"""Tests for configuration management."""


import pytest
import yaml

from nllm.config import (
    create_example_config,
    find_config_file,
    get_default_config,
    load_config,
    load_yaml_file,
    merge_cli_config,
    resolve_models,
    validate_config,
)
from nllm.models import NllmConfig
from nllm.utils import ConfigError


class TestLoadYamlFile:
    """Test YAML file loading."""

    def test_load_valid_yaml(self, tmp_path):
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_data = {"models": ["gpt-4"], "defaults": {"timeout": 60}}
        config_file.write_text(yaml.dump(config_data))

        result = load_yaml_file(config_file)
        assert result == config_data

    def test_load_empty_yaml(self, tmp_path):
        """Test loading empty YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        result = load_yaml_file(config_file)
        assert result == {}

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content:")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_yaml_file(config_file)

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading nonexistent file."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigError, match="Config file not found"):
            load_yaml_file(config_file)

    def test_load_non_dict_yaml(self, tmp_path):
        """Test loading YAML that's not a dictionary."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2")

        with pytest.raises(ConfigError, match="must contain a YAML object"):
            load_yaml_file(config_file)


class TestFindConfigFile:
    """Test config file finding logic."""

    def test_explicit_path_exists(self, tmp_path):
        """Test explicit path that exists."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("test: true")

        result = find_config_file(str(config_file))
        assert result == config_file

    def test_explicit_path_not_exists(self, tmp_path):
        """Test explicit path that doesn't exist."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigError, match="Specified config file not found"):
            find_config_file(str(config_file))

    def test_no_config_files(self, monkeypatch, tmp_path):
        """Test when no config files exist."""
        # Mock CONFIG_FILES to use temp directory
        monkeypatch.setattr(
            "nllm.config.CONFIG_FILES",
            [tmp_path / ".nllm-config.yaml", tmp_path / "config.yaml"],
        )

        result = find_config_file()
        assert result is None

    def test_first_config_file_exists(self, monkeypatch, tmp_path):
        """Test when first config file in precedence exists."""
        config_file1 = tmp_path / ".nllm-config.yaml"
        config_file2 = tmp_path / "config.yaml"

        config_file1.write_text("test: true")

        monkeypatch.setattr("nllm.config.CONFIG_FILES", [config_file1, config_file2])

        result = find_config_file()
        assert result == config_file1


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_with_explicit_path(self, tmp_path):
        """Test loading config with explicit path."""
        config_file = tmp_path / "custom.yaml"
        config_data = {"models": ["gpt-4"], "defaults": {"parallel": 2}}
        config_file.write_text(yaml.dump(config_data))

        config, files_used = load_config(str(config_file))
        assert config.models == ["gpt-4"]
        assert config.parallel == 2
        assert files_used == [str(config_file)]

    def test_load_with_default_location(self, monkeypatch, tmp_path):
        """Test loading config from default location."""
        config_file = tmp_path / ".nllm-config.yaml"
        config_data = {"models": ["claude-3-sonnet"]}
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.setattr("nllm.config.CONFIG_FILES", [config_file])

        config, files_used = load_config()
        assert config.models == ["claude-3-sonnet"]
        assert files_used == [str(config_file)]

    def test_load_no_config_file(self, monkeypatch, tmp_path):
        """Test loading when no config file exists."""
        monkeypatch.setattr(
            "nllm.config.CONFIG_FILES",
            [tmp_path / "nonexistent1.yaml", tmp_path / "nonexistent2.yaml"],
        )

        config, files_used = load_config()
        assert isinstance(config, NllmConfig)
        assert config.models == []
        assert files_used == []

    def test_load_invalid_config_file_explicit(self, tmp_path):
        """Test loading invalid config file with explicit path."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml:")

        with pytest.raises(ConfigError):
            load_config(str(config_file))

    def test_load_invalid_config_file_default(self, monkeypatch, tmp_path):
        """Test loading invalid config file from default location."""
        config_file = tmp_path / ".nllm-config.yaml"
        config_file.write_text("invalid: yaml:")

        monkeypatch.setattr("nllm.config.CONFIG_FILES", [config_file])

        # Should continue with defaults when default config is invalid
        config, files_used = load_config()
        assert isinstance(config, NllmConfig)
        assert files_used == []


class TestValidateConfig:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = NllmConfig(parallel=4, timeout=120, retries=2, outdir="./out")
        # Should not raise
        validate_config(config)

    def test_invalid_parallel(self):
        """Test invalid parallel value."""
        config = NllmConfig(parallel=0)
        with pytest.raises(ConfigError, match="parallel must be at least 1"):
            validate_config(config)

    def test_invalid_timeout(self):
        """Test invalid timeout value."""
        config = NllmConfig(timeout=0)
        with pytest.raises(ConfigError, match="timeout must be at least 1"):
            validate_config(config)

    def test_invalid_retries(self):
        """Test invalid retries value."""
        config = NllmConfig(retries=-1)
        with pytest.raises(ConfigError, match="retries cannot be negative"):
            validate_config(config)

    def test_empty_outdir(self):
        """Test empty outdir."""
        config = NllmConfig(outdir="")
        with pytest.raises(ConfigError, match="outdir cannot be empty"):
            validate_config(config)


class TestResolveModels:
    """Test model resolution logic."""

    def test_cli_models_override_config(self):
        """Test that CLI models override config models."""
        cli_models = ["gpt-4", "claude-3-sonnet"]
        config = NllmConfig(models=["gemini-pro"])

        result = resolve_models(cli_models, config)
        assert result == cli_models

    def test_use_config_models_when_no_cli(self):
        """Test using config models when no CLI models."""
        config = NllmConfig(models=["gpt-4", "claude-3-sonnet"])

        result = resolve_models(None, config)
        assert result == config.models

    def test_no_models_specified(self):
        """Test when no models specified anywhere."""
        config = NllmConfig(models=[])

        result = resolve_models(None, config)
        assert result == []

    def test_empty_cli_models_list(self):
        """Test empty CLI models list."""
        config = NllmConfig(models=["gpt-4"])

        result = resolve_models([], config)
        assert result == []


class TestMergeCliConfig:
    """Test CLI configuration merging."""

    def test_merge_all_options(self):
        """Test merging all CLI options."""
        base_config = NllmConfig(
            models=["gpt-4"],
            parallel=2,
            timeout=60,
            retries=1,
            stream=False,
            outdir="./base",
        )

        merged = merge_cli_config(
            base_config,
            cli_models=["claude-3-sonnet"],
            cli_parallel=4,
            cli_timeout=120,
            cli_retries=3,
            cli_stream=True,
            cli_outdir="./new",
        )

        assert merged.models == ["claude-3-sonnet"]
        assert merged.parallel == 4
        assert merged.timeout == 120
        assert merged.retries == 3
        assert merged.stream is True
        assert merged.outdir == "./new"

    def test_merge_partial_options(self):
        """Test merging partial CLI options."""
        base_config = NllmConfig(models=["gpt-4"], parallel=2, timeout=60, retries=1)

        merged = merge_cli_config(base_config, cli_parallel=8, cli_timeout=300)

        assert merged.models == ["gpt-4"]  # unchanged
        assert merged.parallel == 8  # changed
        assert merged.timeout == 300  # changed
        assert merged.retries == 1  # unchanged

    def test_merge_no_options(self):
        """Test merging with no CLI options."""
        base_config = NllmConfig(models=["gpt-4"], parallel=2)

        merged = merge_cli_config(base_config)

        assert merged.models == base_config.models
        assert merged.parallel == base_config.parallel


class TestCreateExampleConfig:
    """Test example config creation."""

    def test_create_example_config(self):
        """Test creating example configuration."""
        config_text = create_example_config()

        assert "models:" in config_text
        assert "gpt-4" in config_text
        assert "claude-3-sonnet" in config_text
        assert "defaults:" in config_text
        assert "parallel:" in config_text
        assert "timeout:" in config_text

        # Should be valid YAML
        config_data = yaml.safe_load(config_text)
        assert isinstance(config_data, dict)
        assert "models" in config_data
        assert "defaults" in config_data


class TestGetDefaultConfig:
    """Test default config creation."""

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = get_default_config()

        assert isinstance(config, NllmConfig)
        assert config.models == []
        assert config.parallel > 0
        assert config.timeout > 0
        assert config.retries >= 0
        assert isinstance(config.stream, bool)
        assert config.outdir
