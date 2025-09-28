"""Tests for utility functions."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nllm.utils import (
    check_llm_available,
    check_llm_models,
    classify_error,
    construct_llm_command,
    create_timestamped_dir,
    format_duration,
    get_git_sha,
    is_likely_json,
    parse_json_safely,
    redact_secrets_from_args,
    sanitize_filename,
    save_json_safely,
    save_text_safely,
    truncate_stderr,
)


class TestCheckLlmAvailable:
    """Test llm availability checking."""

    @patch("nllm.utils.subprocess.run")
    def test_llm_available(self, mock_run):
        """Test when llm is available."""
        mock_run.return_value = Mock(returncode=0, stdout="llm 0.10.0")

        available, version = check_llm_available()
        assert available is True
        assert version == "llm 0.10.0"

    @patch("nllm.utils.subprocess.run")
    def test_llm_not_available_not_found(self, mock_run):
        """Test when llm command not found."""
        mock_run.side_effect = FileNotFoundError()

        available, version = check_llm_available()
        assert available is False
        assert version is None

    @patch("nllm.utils.subprocess.run")
    def test_llm_not_available_timeout(self, mock_run):
        """Test when llm command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("llm", 10)

        available, version = check_llm_available()
        assert available is False
        assert version is None

    @patch("nllm.utils.subprocess.run")
    def test_llm_not_available_non_zero_exit(self, mock_run):
        """Test when llm returns non-zero exit code."""
        mock_run.return_value = Mock(returncode=1, stdout="")

        available, version = check_llm_available()
        assert available is False
        assert version is None


class TestCheckLlmModels:
    """Test llm models checking."""

    @patch("nllm.utils.subprocess.run")
    def test_get_models_success(self, mock_run):
        """Test successful model list retrieval."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="gpt-4: OpenAI GPT-4\nclaude-3-sonnet: Anthropic Claude 3 Sonnet\n",
        )

        models = check_llm_models()
        assert "gpt-4" in models
        assert "claude-3-sonnet" in models

    @patch("nllm.utils.subprocess.run")
    def test_get_models_failure(self, mock_run):
        """Test failed model list retrieval."""
        mock_run.return_value = Mock(returncode=1, stdout="")

        models = check_llm_models()
        assert models == []

    @patch("nllm.utils.subprocess.run")
    def test_get_models_timeout(self, mock_run):
        """Test model list retrieval timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("llm", 30)

        models = check_llm_models()
        assert models == []


class TestClassifyError:
    """Test error classification."""

    def test_transient_errors(self):
        """Test classification of transient errors."""
        transient_messages = [
            "Connection timeout occurred",
            "Rate limit exceeded",
            "Service unavailable",
            "Gateway timeout",
            "Too many requests",
            "500 Internal Server Error",
        ]

        for message in transient_messages:
            assert classify_error(message) is True

    def test_permanent_errors(self):
        """Test classification of permanent errors."""
        permanent_messages = [
            "Invalid model specified",
            "Authentication failed",
            "API key not found",
            "404 Not Found",
            "Bad request format",
            "Unauthorized access",
        ]

        for message in permanent_messages:
            assert classify_error(message) is False

    def test_unknown_error_classification(self):
        """Test classification of unknown errors (defaults to permanent)."""
        unknown_message = "Some random error message"
        assert classify_error(unknown_message) is False

    def test_case_insensitive_classification(self):
        """Test that error classification is case insensitive."""
        assert classify_error("CONNECTION TIMEOUT") is True
        assert classify_error("Authentication Failed") is False


class TestConstructLlmCommand:
    """Test llm command construction."""

    def test_basic_command_construction(self):
        """Test basic command construction without existing model."""
        command = construct_llm_command("gpt-4", ["prompt text"])
        assert command == ["llm", "-m", "gpt-4", "prompt text"]

    def test_command_with_existing_model(self):
        """Test command construction when model already specified."""
        llm_args = ["-m", "claude-3-sonnet", "prompt text"]
        command = construct_llm_command("gpt-4", llm_args)
        # Should not add another -m flag
        assert command == ["llm", "-m", "claude-3-sonnet", "prompt text"]

    def test_command_with_long_model_flag(self):
        """Test command construction with --model flag."""
        llm_args = ["--model", "claude-3-sonnet", "prompt text"]
        command = construct_llm_command("gpt-4", llm_args)
        # Should not add another model flag
        assert command == ["llm", "--model", "claude-3-sonnet", "prompt text"]

    def test_command_with_other_flags(self):
        """Test command construction with other flags."""
        llm_args = ["-t", "0.7", "--system", "You are helpful", "prompt text"]
        command = construct_llm_command("gpt-4", llm_args)
        expected = ["llm", "-m", "gpt-4", "-t", "0.7", "--system", "You are helpful", "prompt text"]
        assert command == expected


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_sanitize_basic_filename(self):
        """Test sanitizing basic filename."""
        result = sanitize_filename("gpt-4")
        assert result == "gpt-4"

    def test_sanitize_problematic_characters(self):
        """Test sanitizing filename with problematic characters."""
        result = sanitize_filename("model:name/with<>chars")
        assert result == "model_name_with__chars"

    def test_sanitize_long_filename(self):
        """Test sanitizing very long filename."""
        long_name = "a" * 150
        result = sanitize_filename(long_name)
        assert len(result) <= 100

    def test_sanitize_with_whitespace(self):
        """Test sanitizing filename with leading/trailing whitespace."""
        result = sanitize_filename("  model-name  ")
        assert result == "model-name"


class TestTruncateStderr:
    """Test stderr truncation."""

    def test_truncate_short_stderr(self):
        """Test truncating stderr that's already short."""
        stderr = "line1\nline2\nline3"
        result = truncate_stderr(stderr, 5)
        assert result == stderr

    def test_truncate_long_stderr(self):
        """Test truncating long stderr."""
        lines = [f"line{i}" for i in range(20)]
        stderr = "\n".join(lines)
        result = truncate_stderr(stderr, 5)
        result_lines = result.splitlines()
        assert len(result_lines) == 5
        assert result_lines[-1] == "line19"  # Should keep last 5 lines

    def test_truncate_empty_stderr(self):
        """Test truncating empty stderr."""
        result = truncate_stderr("", 5)
        assert result == ""


class TestFormatDuration:
    """Test duration formatting."""

    def test_format_milliseconds(self):
        """Test formatting duration in milliseconds."""
        assert format_duration(500) == "500ms"
        assert format_duration(999) == "999ms"

    def test_format_seconds(self):
        """Test formatting duration in seconds."""
        assert format_duration(1500) == "1.5s"
        assert format_duration(45000) == "45.0s"

    def test_format_minutes(self):
        """Test formatting duration in minutes."""
        assert format_duration(75000) == "1m 15s"
        assert format_duration(125000) == "2m 5s"


class TestGetGitSha:
    """Test git SHA retrieval."""

    @patch("nllm.utils.subprocess.run")
    def test_get_git_sha_success(self, mock_run):
        """Test successful git SHA retrieval."""
        mock_run.return_value = Mock(
            returncode=0, stdout="abcdef1234567890abcdef1234567890abcdef12\n"
        )

        result = get_git_sha()
        assert result == "abcdef123456"  # Should be truncated to 12 chars

    @patch("nllm.utils.subprocess.run")
    def test_get_git_sha_not_git_repo(self, mock_run):
        """Test git SHA retrieval outside git repo."""
        mock_run.return_value = Mock(returncode=128, stdout="")

        result = get_git_sha()
        assert result is None

    @patch("nllm.utils.subprocess.run")
    def test_get_git_sha_command_not_found(self, mock_run):
        """Test git SHA retrieval when git not available."""
        mock_run.side_effect = FileNotFoundError()

        result = get_git_sha()
        assert result is None


class TestSafeFileOperations:
    """Test safe file operations."""

    def test_save_json_safely(self, tmp_path):
        """Test safe JSON saving."""
        data = {"test": "value", "number": 42}
        file_path = tmp_path / "test.json"

        save_json_safely(data, file_path)

        assert file_path.exists()
        with file_path.open() as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_save_text_safely(self, tmp_path):
        """Test safe text saving."""
        content = "Hello, world!\nThis is a test."
        file_path = tmp_path / "test.txt"

        save_text_safely(content, file_path)

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content

    def test_save_json_safely_atomic(self, tmp_path):
        """Test that JSON saving is atomic (temp file cleaned up on error)."""
        file_path = tmp_path / "test.json"

        # Create invalid data that will cause JSON encoding to fail
        class InvalidData:
            pass

        with pytest.raises(TypeError):
            save_json_safely({"invalid": InvalidData()}, file_path)

        # Should not create the target file or leave temp files
        assert not file_path.exists()
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0


class TestRedactSecretsFromArgs:
    """Test secret redaction from command line arguments."""

    def test_redact_api_key_flag(self):
        """Test redacting API key with flag."""
        args = ["llm", "--api-key", "secret123", "prompt"]
        result = redact_secrets_from_args(args)
        assert result == ["llm", "--api-key", "***REDACTED***", "prompt"]

    def test_redact_inline_secret(self):
        """Test redacting inline secret."""
        args = ["llm", "--api-key=secret123", "prompt"]
        result = redact_secrets_from_args(args)
        assert result == ["llm", "--api-key=***REDACTED***", "prompt"]

    def test_redact_obvious_api_key(self):
        """Test redacting obvious API key pattern."""
        args = ["llm", "sk-1234567890abcdef1234567890abcdef", "prompt"]
        result = redact_secrets_from_args(args)
        assert result == ["llm", "***REDACTED***", "prompt"]

    def test_no_secrets_to_redact(self):
        """Test when no secrets need redacting."""
        args = ["llm", "-m", "gpt-4", "Hello world"]
        result = redact_secrets_from_args(args)
        assert result == args

    def test_redact_multiple_secrets(self):
        """Test redacting multiple secrets."""
        args = ["llm", "--api-key", "secret1", "--token", "secret2", "prompt"]
        result = redact_secrets_from_args(args)
        expected = ["llm", "--api-key", "***REDACTED***", "--token", "***REDACTED***", "prompt"]
        assert result == expected


class TestCreateTimestampedDir:
    """Test timestamped directory creation."""

    def test_create_unique_dir(self, tmp_path):
        """Test creating unique timestamped directory."""
        base_dir = str(tmp_path / "test-runs")

        result = create_timestamped_dir(base_dir)

        assert result.exists()
        assert result.is_dir()
        assert result.parent == Path(base_dir)

    def test_create_dir_with_collision(self, tmp_path):
        """Test creating directory when timestamp collision occurs."""
        base_dir = str(tmp_path / "test-runs")

        # Create the first directory
        dir1 = create_timestamped_dir(base_dir)

        # Mock datetime to return same timestamp
        with patch("nllm.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = dir1.name

            # Should create directory with suffix
            dir2 = create_timestamped_dir(base_dir)

            assert dir1.exists()
            assert dir2.exists()
            assert dir1 != dir2


class TestJsonUtilities:
    """Test JSON-related utilities."""

    def test_is_likely_json_object(self):
        """Test detecting JSON objects."""
        assert is_likely_json('{"key": "value"}') is True
        assert is_likely_json('  {"key": "value"}  ') is True

    def test_is_likely_json_array(self):
        """Test detecting JSON arrays."""
        assert is_likely_json("[1, 2, 3]") is True
        assert is_likely_json("  [1, 2, 3]  ") is True

    def test_is_not_likely_json(self):
        """Test detecting non-JSON text."""
        assert is_likely_json("Hello world") is False
        assert is_likely_json('{"incomplete": ') is False

    def test_parse_json_safely_valid(self):
        """Test parsing valid JSON."""
        result = parse_json_safely('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_safely_invalid(self):
        """Test parsing invalid JSON."""
        result = parse_json_safely('{"invalid": json}')
        assert result is None

    def test_parse_json_safely_empty(self):
        """Test parsing empty string."""
        result = parse_json_safely("")
        assert result is None
