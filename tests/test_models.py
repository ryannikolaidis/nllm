"""Tests for data models."""

import json
from pathlib import Path
from unittest.mock import patch

from nllm.models import ExecutionContext, ModelResult, NllmConfig, RunManifest


class TestModelResult:
    """Test ModelResult data model."""

    def test_create_basic_result(self):
        """Test creating basic model result."""
        result = ModelResult(
            model="gpt-4",
            status="ok",
            duration_ms=1500,
            exit_code=0,
            text="Hello, world!",
        )

        assert result.model == "gpt-4"
        assert result.status == "ok"
        assert result.duration_ms == 1500
        assert result.exit_code == 0
        assert result.text == "Hello, world!"
        assert result.meta == {}
        assert result.command == []
        assert result.stderr_tail == ""
        assert result.json is None

    def test_create_result_with_metadata(self):
        """Test creating result with metadata."""
        result = ModelResult(
            model="claude-3-sonnet",
            status="ok",
            duration_ms=2000,
            exit_code=0,
            text="Response text",
            meta={"tokens_input": 10, "tokens_output": 20},
            command=["llm", "-m", "claude-3-sonnet", "prompt"],
            stderr_tail="Usage: 30 tokens",
        )

        assert result.meta["tokens_input"] == 10
        assert result.meta["tokens_output"] == 20
        assert result.command == ["llm", "-m", "claude-3-sonnet", "prompt"]
        assert result.stderr_tail == "Usage: 30 tokens"

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ModelResult(
            model="gpt-4",
            status="error",
            duration_ms=1000,
            exit_code=1,
            text="",
            meta={"error": True},
            command=["llm", "-m", "gpt-4", "prompt"],
            stderr_tail="Error occurred",
        )

        result_dict = result.to_dict()

        expected = {
            "model": "gpt-4",
            "status": "error",
            "duration_ms": 1000,
            "exit_code": 1,
            "text": "",
            "meta": {"error": True},
            "command": ["llm", "-m", "gpt-4", "prompt"],
            "stderr_tail": "Error occurred",
            "json": None,
        }

        assert result_dict == expected

    def test_serialization(self):
        """Test that result can be serialized to JSON."""
        result = ModelResult(
            model="gpt-4",
            status="ok",
            duration_ms=1500,
            exit_code=0,
            text="Hello",
            meta={"tokens": 5},
        )

        # Should not raise
        json_str = json.dumps(result.to_dict())
        loaded = json.loads(json_str)
        assert loaded["model"] == "gpt-4"

    def test_create_result_with_json(self):
        """Test creating result with extracted JSON."""
        json_data = {"status": "success", "data": [1, 2, 3]}
        result = ModelResult(
            model="gpt-4",
            status="ok",
            duration_ms=1000,
            exit_code=0,
            text='{"status": "success", "data": [1, 2, 3]}',
            json=json_data,
        )

        assert result.json == json_data
        assert result.text == '{"status": "success", "data": [1, 2, 3]}'

    def test_to_dict_with_json(self):
        """Test converting result with JSON to dictionary."""
        json_data = {"result": "test", "score": 95}
        result = ModelResult(
            model="claude-3-sonnet",
            status="ok",
            duration_ms=2000,
            exit_code=0,
            text="Analysis complete: {'result': 'test', 'score': 95}",
            json=json_data,
        )

        result_dict = result.to_dict()

        assert result_dict["json"] == json_data
        assert result_dict["model"] == "claude-3-sonnet"
        assert result_dict["text"] == "Analysis complete: {'result': 'test', 'score': 95}"

    def test_serialization_with_json(self):
        """Test that result with JSON can be serialized."""
        json_data = {"nested": {"values": [1, 2, 3]}, "bool": True}
        result = ModelResult(
            model="gpt-4",
            status="ok",
            duration_ms=1500,
            exit_code=0,
            text="Complex response with JSON",
            json=json_data,
        )

        # Should not raise
        json_str = json.dumps(result.to_dict())
        loaded = json.loads(json_str)

        assert loaded["json"]["nested"]["values"] == [1, 2, 3]
        assert loaded["json"]["bool"] is True


class TestRunManifest:
    """Test RunManifest data model."""

    def test_create_basic_manifest(self):
        """Test creating basic manifest."""
        manifest = RunManifest(
            cli_args=["prompter", "-m", "gpt-4", "prompt"],
            resolved_models=["gpt-4"],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        assert manifest.cli_args == ["prompter", "-m", "gpt-4", "prompt"]
        assert manifest.resolved_models == ["gpt-4"]
        assert manifest.timestamp == "2023-01-01T12:00:00"
        assert manifest.hostname == "test-host"
        assert manifest.git_sha is None
        assert manifest.config_paths_used == []

    def test_create_with_optional_fields(self):
        """Test creating manifest with optional fields."""
        manifest = RunManifest(
            cli_args=["prompter", "prompt"],
            resolved_models=["gpt-4", "claude-3-sonnet"],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
            git_sha="abc123def456",
            config_paths_used=["/path/to/config.yaml"],
            llm_version="0.10.0",
        )

        assert manifest.git_sha == "abc123def456"
        assert manifest.config_paths_used == ["/path/to/config.yaml"]
        assert manifest.llm_version == "0.10.0"

    @patch("nllm.models.socket.gethostname")
    @patch("nllm.models.datetime")
    @patch("nllm.models.Path.cwd")
    def test_create_with_current_info(self, mock_cwd, mock_datetime, mock_hostname):
        """Test creating manifest with current system info."""
        mock_hostname.return_value = "current-host"
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00.123456"
        mock_cwd.return_value = Path("/current/dir")

        manifest = RunManifest.create(
            cli_args=["prompter", "prompt"],
            resolved_models=["gpt-4"],
            config_paths_used=[],
        )

        assert manifest.hostname == "current-host"
        assert manifest.timestamp == "2023-01-01T12:00:00.123456"
        assert manifest.working_directory == "/current/dir"

    def test_to_dict(self):
        """Test converting manifest to dictionary."""
        manifest = RunManifest(
            cli_args=["prompter", "-m", "gpt-4", "prompt"],
            resolved_models=["gpt-4"],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
            git_sha="abc123",
            config_paths_used=["/config.yaml"],
            llm_version="0.10.0",
            os_info="Linux-5.4.0",
            working_directory="/work/dir",
        )

        result_dict = manifest.to_dict()

        expected = {
            "cli_args": ["prompter", "-m", "gpt-4", "prompt"],
            "resolved_models": ["gpt-4"],
            "timestamp": "2023-01-01T12:00:00",
            "hostname": "test-host",
            "git_sha": "abc123",
            "config_paths_used": ["/config.yaml"],
            "llm_version": "0.10.0",
            "os_info": "Linux-5.4.0",
            "working_directory": "/work/dir",
        }

        assert result_dict == expected

    def test_serialization(self):
        """Test that manifest can be serialized to JSON."""
        manifest = RunManifest(
            cli_args=["prompter", "prompt"],
            resolved_models=["gpt-4"],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        # Should not raise
        json_str = json.dumps(manifest.to_dict())
        loaded = json.loads(json_str)
        assert loaded["hostname"] == "test-host"


class TestNllmConfig:
    """Test NllmConfig data model."""

    def test_create_default_config(self):
        """Test creating config with defaults."""
        config = NllmConfig()

        assert config.models == []
        assert config.parallel == 4
        assert config.timeout == 120
        assert config.retries == 0
        assert config.stream is True
        assert config.outdir == "./nllm-runs"
        assert config.costs == {}

    def test_create_custom_config(self):
        """Test creating config with custom values."""
        config = NllmConfig(
            models=["gpt-4", "claude-3-sonnet"],
            parallel=8,
            timeout=300,
            retries=2,
            stream=False,
            outdir="/custom/output",
            costs={"gpt-4": {"input_per_1k": 0.03}},
        )

        assert config.models == ["gpt-4", "claude-3-sonnet"]
        assert config.parallel == 8
        assert config.timeout == 300
        assert config.retries == 2
        assert config.stream is False
        assert config.outdir == "/custom/output"
        assert config.costs == {"gpt-4": {"input_per_1k": 0.03}}

    def test_from_dict_basic(self):
        """Test creating config from dictionary."""
        data = {
            "models": ["gpt-4"],
            "defaults": {"parallel": 6, "timeout": 180},
        }

        config = NllmConfig.from_dict(data)

        assert len(config.models) == 1
        assert config.models[0].name == "gpt-4"
        assert config.models[0].options == []
        assert config.parallel == 6
        assert config.timeout == 180
        # Other fields should have defaults
        assert config.retries == 0
        assert config.stream is True

    def test_from_dict_with_costs(self):
        """Test creating config from dictionary with costs."""
        data = {
            "models": ["gpt-4"],
            "costs": {"gpt-4": {"input_per_1k": 0.03, "output_per_1k": 0.06}},
        }

        config = NllmConfig.from_dict(data)

        assert config.costs == {"gpt-4": {"input_per_1k": 0.03, "output_per_1k": 0.06}}

    def test_from_dict_empty(self):
        """Test creating config from empty dictionary."""
        config = NllmConfig.from_dict({})

        # Should use all defaults
        assert config.models == []
        assert config.parallel == 4
        assert config.timeout == 120

    def test_merge_cli_args_all(self):
        """Test merging all CLI arguments."""
        config = NllmConfig(
            models=["gpt-4"],
            parallel=2,
            timeout=60,
            retries=1,
            stream=False,
            outdir="./old",
        )

        merged = config.merge_cli_args(
            models=["claude-3-sonnet"],
            parallel=8,
            timeout=300,
            retries=3,
            stream=True,
            outdir="./new",
        )

        # Original should be unchanged
        assert config.models == ["gpt-4"]
        assert config.parallel == 2

        # New config should have merged values
        assert merged.models == ["claude-3-sonnet"]
        assert merged.parallel == 8
        assert merged.timeout == 300
        assert merged.retries == 3
        assert merged.stream is True
        assert merged.outdir == "./new"

    def test_merge_cli_args_partial(self):
        """Test merging partial CLI arguments."""
        config = NllmConfig(models=["gpt-4"], parallel=4, timeout=120)

        merged = config.merge_cli_args(parallel=8)

        assert merged.models == ["gpt-4"]  # unchanged
        assert merged.parallel == 8  # changed
        assert merged.timeout == 120  # unchanged

    def test_merge_cli_args_none(self):
        """Test merging when no CLI arguments provided."""
        config = NllmConfig(models=["gpt-4"], parallel=4)

        merged = config.merge_cli_args()

        # Should be identical
        assert merged.models == config.models
        assert merged.parallel == config.parallel


class TestExecutionContext:
    """Test ExecutionContext data model."""

    def test_create_basic_context(self, tmp_path):
        """Test creating basic execution context."""
        config = NllmConfig(models=["gpt-4"])
        manifest = RunManifest(
            cli_args=["prompter", "prompt"],
            resolved_models=["gpt-4"],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        context = ExecutionContext(
            config=config,
            llm_args=["prompt"],
            output_dir=tmp_path,
            manifest=manifest,
        )

        assert context.config == config
        assert context.llm_args == ["prompt"]
        assert context.output_dir == tmp_path
        assert context.manifest == manifest
        assert context.quiet is False
        assert context.dry_run is False
        assert context.raw_output is False

    def test_create_context_with_options(self, tmp_path):
        """Test creating context with optional flags."""
        config = NllmConfig()
        manifest = RunManifest(
            cli_args=["prompter"],
            resolved_models=[],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        context = ExecutionContext(
            config=config,
            llm_args=[],
            output_dir=tmp_path,
            manifest=manifest,
            quiet=True,
            dry_run=True,
            raw_output=True,
        )

        assert context.quiet is True
        assert context.dry_run is True
        assert context.raw_output is True

    def test_get_model_output_paths(self, tmp_path):
        """Test getting model output paths."""
        config = NllmConfig()
        manifest = RunManifest(
            cli_args=["prompter"],
            resolved_models=[],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        context = ExecutionContext(
            config=config,
            llm_args=[],
            output_dir=tmp_path,
            manifest=manifest,
        )

        stdout_path, stderr_path = context.get_model_output_paths("gpt-4")

        expected_stdout = tmp_path / "raw" / "gpt-4.stdout.txt"
        expected_stderr = tmp_path / "raw" / "gpt-4.stderr.txt"

        assert stdout_path == expected_stdout
        assert stderr_path == expected_stderr
        assert stdout_path.parent.exists()  # Should create raw directory

    def test_get_results_dir(self, tmp_path):
        """Test getting results directory."""
        config = NllmConfig()
        manifest = RunManifest(
            cli_args=["prompter"],
            resolved_models=[],
            timestamp="2023-01-01T12:00:00",
            hostname="test-host",
        )

        context = ExecutionContext(
            config=config,
            llm_args=[],
            output_dir=tmp_path,
            manifest=manifest,
        )

        results_dir = context.get_results_dir()

        expected_dir = tmp_path / "results"
        assert results_dir == expected_dir
        assert results_dir.exists()  # Should create results directory
