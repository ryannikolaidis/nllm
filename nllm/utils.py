"""Utility functions and error handling for nllm."""

import asyncio
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .constants import (
    OUTPUT_DIR_TIMESTAMP_FORMAT,
    PERMANENT_ERROR_PATTERNS,
    TRANSIENT_ERROR_PATTERNS,
)


class NllmError(Exception):
    """Base exception for nllm errors."""

    pass


class ConfigError(NllmError):
    """Configuration-related errors."""

    pass


class ExecutionError(NllmError):
    """Execution-related errors."""

    pass


def check_llm_available() -> tuple[bool, str | None]:
    """Check if llm command is available and get version."""
    try:
        result = subprocess.run(["llm", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False, None


def check_llm_models() -> list[str]:
    """Get list of available models from llm command."""
    try:
        result = subprocess.run(["llm", "models"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            # Parse model names from output - typically one per line
            models = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extract model name (first word/token, remove colon if present)
                    model_name = line.split()[0] if line.split() else line
                    model_name = model_name.rstrip(":")
                    models.append(model_name)
            return models
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return []


def classify_error(stderr_content: str) -> bool:
    """Classify error as transient (retryable) or permanent."""
    stderr_lower = stderr_content.lower()

    # Check for permanent error patterns first
    for pattern in PERMANENT_ERROR_PATTERNS:
        if pattern in stderr_lower:
            return False  # Permanent error, not retryable

    # Check for transient error patterns
    for pattern in TRANSIENT_ERROR_PATTERNS:
        if pattern in stderr_lower:
            return True  # Transient error, retryable

    # Default: assume permanent if we can't classify
    return False


async def retry_with_backoff(
    coro_func, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
):
    """Retry a coroutine with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except Exception as e:
            if attempt == max_retries:
                raise e

            # Calculate delay with exponential backoff
            delay = min(base_delay * (2**attempt), max_delay)
            await asyncio.sleep(delay)


def create_timestamped_dir(base_dir: str) -> Path:
    """Create a timestamped output directory."""
    timestamp = datetime.now().strftime(OUTPUT_DIR_TIMESTAMP_FORMAT)
    output_dir = Path(base_dir) / timestamp

    # Ensure directory doesn't exist (handle race conditions)
    counter = 1
    original_dir = output_dir
    while output_dir.exists():
        output_dir = original_dir.with_name(f"{original_dir.name}_{counter}")
        counter += 1

    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def construct_llm_command(model: str, llm_args: list[str], model_options: list[str] | None = None) -> list[str]:
    """Construct llm command for a specific model with per-model options."""
    command = ["llm"]

    # If model is already specified in llm_args, don't add it again
    has_model = False
    for i, arg in enumerate(llm_args):
        if arg in ("-m", "--model") and i + 1 < len(llm_args):
            has_model = True
            break

    if not has_model:
        command.extend(["-m", model])

    # Add model-specific options before global llm_args
    if model_options:
        command.extend(model_options)

    command.extend(llm_args)
    return command


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe as a filename."""
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized.strip()


def truncate_stderr(stderr: str, max_lines: int = 10) -> str:
    """Truncate stderr to last N lines for compact error reporting."""
    lines = stderr.splitlines()
    if len(lines) <= max_lines:
        return stderr

    return "\n".join(lines[-max_lines:])


def format_duration(duration_ms: int) -> str:
    """Format duration in milliseconds to human-readable string."""
    if duration_ms < 1000:
        return f"{duration_ms}ms"
    elif duration_ms < 60000:
        return f"{duration_ms / 1000:.1f}s"
    else:
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) // 1000
        return f"{minutes}m {seconds}s"


def get_git_sha() -> str | None:
    """Get current git SHA if in a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path.cwd(),
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]  # Short SHA
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return None


def save_json_safely(data: dict, file_path: Path) -> None:
    """Save JSON data safely with atomic write."""
    temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(file_path)
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise


def save_text_safely(content: str, file_path: Path) -> None:
    """Save text content safely with atomic write."""
    temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            f.write(content)
        temp_file.replace(file_path)
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise


def redact_secrets_from_args(args: list[str]) -> list[str]:
    """Redact potential secrets from command line arguments."""
    redacted = []
    redact_next = False

    for arg in args:
        if redact_next:
            redacted.append("***REDACTED***")
            redact_next = False
            continue

        # Check for flags that might precede secrets
        if arg.lower() in ("--api-key", "--token", "--password", "--secret"):
            redacted.append(arg)
            redact_next = True
            continue

        # Check for inline secrets (key=value format)
        if "=" in arg:
            key, value = arg.split("=", 1)
            if any(
                secret_word in key.lower() for secret_word in ["key", "token", "password", "secret"]
            ):
                redacted.append(f"{key}=***REDACTED***")
                continue

        # Check for obvious API key patterns
        if re.match(r"sk-[a-zA-Z0-9]{32,}", arg) or re.match(r"[a-zA-Z0-9]{32,}", arg):
            redacted.append("***REDACTED***")
            continue

        redacted.append(arg)

    return redacted


def get_terminal_width() -> int:
    """Get terminal width, with fallback."""
    try:
        return shutil.get_terminal_size().columns
    except OSError:
        return 80  # Fallback width


def ensure_directory_exists(path: Path) -> None:
    """Ensure directory exists, creating parent directories if needed."""
    path.mkdir(parents=True, exist_ok=True)


def is_likely_json(text: str) -> bool:
    """Check if text looks like JSON (for parsing llm output)."""
    text = text.strip()
    return (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    )


def parse_json_safely(text: str) -> dict | None:
    """Try to parse JSON, return None if invalid."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
