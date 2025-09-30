"""Constants and defaults for nllm."""

from pathlib import Path

# Default configuration values
DEFAULT_TIMEOUT = None  # No timeout by default
DEFAULT_RETRIES = 0
DEFAULT_STREAM = True
DEFAULT_OUTDIR = "./nllm-runs"

# Configuration file precedence
CONFIG_FILES = [
    Path("./.nllm-config.yaml"),
    Path.home() / ".nllm" / "config.yaml",
]

# Output file patterns
OUTPUT_DIR_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
MANIFEST_FILE = "manifest.json"
RESULTS_JSONL_FILE = "results.jsonl"
RAW_DIR = "raw"
RESULTS_DIR = "results"

# Error classification patterns - used to determine if errors are retryable
TRANSIENT_ERROR_PATTERNS = [
    "connection",
    "timeout",
    "5xx",
    "500 internal server error",
    "rate limit",
    "temporary",
    "backoff",
    "service unavailable",
    "gateway timeout",
    "too many requests",
]

PERMANENT_ERROR_PATTERNS = [
    "invalid model",
    "authentication",
    "api key",
    "not found",
    "4xx",
    "unauthorized",
    "forbidden",
    "bad request",
]

# CLI help messages
CLI_DESCRIPTION = """
Multi-model fan-out wrapper for the `llm` CLI tool.

Execute the same prompt across multiple AI models concurrently, with structured output
and streaming console feedback. Supports all llm flags and options transparently.

Examples:
  nllm -m gpt-4 -m claude-3-sonnet -- "Explain quantum computing"
  nllm -- -m gpt-4 -t 0.2 --system "You are helpful" "Write a haiku"
  nllm -c my-config.yaml -- "What is the capital of France?"
"""

MODEL_HELP = "Model to use (repeatable). Overrides config file if specified."
CONFIG_HELP = "Path to config file (default: ./.nllm-config.yaml or ~/.nllm/config.yaml)"
OUTDIR_HELP = "Output directory for results (default: ./nllm-runs/<timestamp>)"
TIMEOUT_HELP = "Per-model timeout in seconds (default: no timeout)"
RETRIES_HELP = f"Per-model retries for transient errors (default: {DEFAULT_RETRIES})"
STREAM_HELP = "Stream model outputs to console as they arrive (default: true)"
RAW_HELP = "Save raw stdout/stderr files in addition to parsed content"
DRY_RUN_HELP = "Show resolved commands without executing"
QUIET_HELP = "Reduce console output (errors still shown)"

# Error messages
ERROR_NO_MODELS = "No models specified. Use -m/--model flags or configure models in a config file."
ERROR_LLM_NOT_FOUND = "The 'llm' command was not found. Please install the llm package."
ERROR_CONFIG_NOT_FOUND = "Config file not found: {path}"
ERROR_CONFIG_INVALID = "Invalid config file format: {path}"
ERROR_MODEL_TIMEOUT = "Model {model} timed out after {timeout} seconds"
ERROR_MODEL_FAILED = "Model {model} failed with exit code {exit_code}"

# Success messages
SUCCESS_ALL_MODELS = "All {count} models completed successfully"
SUCCESS_PARTIAL = "{success} of {total} models completed successfully"
SUCCESS_ARTIFACTS = "Artifacts saved to: {path}"

# Status indicators (for rich console output)
STATUS_SUCCESS = "✓"
STATUS_ERROR = "✗"
STATUS_TIMEOUT = "⏰"
STATUS_RUNNING = "⟳"

# Streaming prefixes
MODEL_PREFIX_FORMAT = "[{model}]"
DRY_RUN_PREFIX = "DRY RUN:"
