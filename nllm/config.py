"""Configuration management for nllm."""

from __future__ import annotations

from pathlib import Path

import yaml

from .constants import (
    CONFIG_FILES,
    DEFAULT_OUTDIR,
    DEFAULT_PARALLEL,
    DEFAULT_RETRIES,
    DEFAULT_STREAM,
    DEFAULT_TIMEOUT,
)
from .models import NllmConfig
from .utils import ConfigError


def load_yaml_file(file_path: Path) -> dict:
    """Load and parse a YAML configuration file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}
            if not isinstance(content, dict):
                raise ConfigError(f"Config file must contain a YAML object: {file_path}")
            return content
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file {file_path}: {e}") from e
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {file_path}") from None
    except Exception as e:
        raise ConfigError(f"Error reading config file {file_path}: {e}") from e


def find_config_file(explicit_path: str | None = None) -> Path | None:
    """Find the configuration file using precedence rules."""
    # 1. Explicit path from CLI
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise ConfigError(f"Specified config file not found: {path}")
        return path

    # 2. Check default locations in order
    for config_path in CONFIG_FILES:
        if config_path.exists():
            return config_path

    return None


def load_config(explicit_path: str | None = None) -> tuple[NllmConfig, list[str]]:
    """Load configuration with precedence handling.

    Returns:
        Tuple of (config, list_of_config_files_used)
    """
    config_files_used = []

    # Try to find and load config file
    config_file = find_config_file(explicit_path)
    if config_file:
        try:
            config_data = load_yaml_file(config_file)
            config_files_used.append(str(config_file))
            return NllmConfig.from_dict(config_data), config_files_used
        except ConfigError:
            # If explicit path was given, re-raise the error
            if explicit_path:
                raise
            # Otherwise, continue with defaults
            pass

    # No config file found or failed to load - use defaults
    return NllmConfig(), config_files_used


def validate_config(config: NllmConfig) -> None:
    """Validate configuration values."""
    if config.parallel < 1:
        raise ConfigError("parallel must be at least 1")

    if config.timeout < 1:
        raise ConfigError("timeout must be at least 1 second")

    if config.retries < 0:
        raise ConfigError("retries cannot be negative")

    if not config.outdir:
        raise ConfigError("outdir cannot be empty")


def create_example_config() -> str:
    """Create an example configuration file content."""
    return """# Prompter configuration file
# This file configures default behavior for the nllm CLI

# List of models to use if none specified on command line
models:
  - "gpt-4"
  - "claude-3-sonnet"
  - "gemini-pro"

# Default settings
defaults:
  parallel: 3          # Maximum concurrent models
  timeout: 120         # Per-model timeout in seconds
  retries: 0          # Per-model retries for transient errors
  stream: true        # Stream outputs to console
  outdir: "./nllm-runs"  # Base output directory

# Optional: Cost tracking per model (estimates)
# costs:
#   gpt-4:
#     input_per_1k: 0.03
#     output_per_1k: 0.06
#   claude-3-sonnet:
#     input_per_1k: 0.003
#     output_per_1k: 0.015
"""


def resolve_models(cli_models: list[str] | None, config: NllmConfig) -> list[str]:
    """Resolve final model list from CLI args and config."""
    # CLI models override config models (including empty list)
    if cli_models is not None:
        return cli_models

    # Use config models
    if config.models:
        return config.models

    # No models specified anywhere
    return []


def merge_cli_config(
    config: NllmConfig,
    cli_models: list[str] | None = None,
    cli_parallel: int | None = None,
    cli_timeout: int | None = None,
    cli_retries: int | None = None,
    cli_stream: bool | None = None,
    cli_outdir: str | None = None,
) -> NllmConfig:
    """Merge CLI arguments into configuration."""
    return config.merge_cli_args(
        models=cli_models,
        parallel=cli_parallel,
        timeout=cli_timeout,
        retries=cli_retries,
        stream=cli_stream,
        outdir=cli_outdir,
    )


def save_config_file(config_path: Path, create_parents: bool = True) -> None:
    """Save an example config file."""
    if create_parents:
        config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as f:
        f.write(create_example_config())


def get_default_config() -> NllmConfig:
    """Get a configuration with hardcoded defaults."""
    return NllmConfig(
        models=[],
        parallel=DEFAULT_PARALLEL,
        timeout=DEFAULT_TIMEOUT,
        retries=DEFAULT_RETRIES,
        stream=DEFAULT_STREAM,
        outdir=DEFAULT_OUTDIR,
    )
