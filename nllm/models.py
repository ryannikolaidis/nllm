"""Data models for nllm results and manifest."""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


@dataclass
class ModelResult:
    """Result from running a single model."""

    model: str
    status: Literal["ok", "error", "timeout"]
    duration_ms: int
    exit_code: int
    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    command: list[str] = field(default_factory=list)
    stderr_tail: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "text": self.text,
            "meta": self.meta,
            "command": self.command,
            "stderr_tail": self.stderr_tail,
        }


@dataclass
class NllmResults:
    """Results returned from the Python API."""

    results: list[ModelResult]
    manifest: RunManifest
    success_count: int
    total_count: int
    exit_code: int

    @property
    def success(self) -> bool:
        """Whether all models completed successfully."""
        return self.exit_code == 0

    @property
    def failed_models(self) -> list[str]:
        """List of models that failed or timed out."""
        return [r.model for r in self.results if r.status in ("error", "timeout")]

    @property
    def successful_models(self) -> list[str]:
        """List of models that completed successfully."""
        return [r.model for r in self.results if r.status == "ok"]

    def get_result(self, model: str) -> ModelResult | None:
        """Get result for a specific model."""
        for result in self.results:
            if result.model == model:
                return result
        return None


@dataclass
class RunManifest:
    """Manifest for a complete nllm run."""

    cli_args: list[str]
    resolved_models: list[str]
    timestamp: str
    hostname: str
    git_sha: str | None = None
    config_paths_used: list[str] = field(default_factory=list)
    llm_version: str | None = None
    os_info: str = field(default_factory=lambda: platform.platform())
    working_directory: str = field(default_factory=lambda: str(Path.cwd()))

    @classmethod
    def create(
        cls,
        cli_args: list[str],
        resolved_models: list[str],
        config_paths_used: list[str],
        git_sha: str | None = None,
        llm_version: str | None = None,
    ) -> RunManifest:
        """Create a new manifest with current system info."""
        return cls(
            cli_args=cli_args,
            resolved_models=resolved_models,
            timestamp=datetime.now().isoformat(),
            hostname=socket.gethostname(),
            git_sha=git_sha,
            config_paths_used=config_paths_used,
            llm_version=llm_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cli_args": self.cli_args,
            "resolved_models": self.resolved_models,
            "timestamp": self.timestamp,
            "hostname": self.hostname,
            "git_sha": self.git_sha,
            "config_paths_used": self.config_paths_used,
            "llm_version": self.llm_version,
            "os_info": self.os_info,
            "working_directory": self.working_directory,
        }


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    name: str
    options: list[str] = field(default_factory=list)

    @classmethod
    def from_string(cls, model_str: str) -> ModelConfig:
        """Create ModelConfig from a simple string."""
        return cls(name=model_str, options=[])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        """Create ModelConfig from dictionary."""
        if "name" not in data:
            raise ValueError("Model config must have 'name' field")
        return cls(
            name=data["name"],
            options=data.get("options", [])
        )


@dataclass
class NllmConfig:
    """Configuration for nllm runs."""

    models: list[ModelConfig] = field(default_factory=list)
    parallel: int = 4
    timeout: int = 120
    retries: int = 0
    stream: bool = True
    outdir: str = "./nllm-runs"
    costs: dict[str, dict[str, float]] = field(default_factory=dict)

    def get_model_names(self) -> list[str]:
        """Get list of model names."""
        return [model.name for model in self.models]

    def get_model_config(self, model_name: str) -> ModelConfig | None:
        """Get configuration for a specific model."""
        for model in self.models:
            if model.name == model_name:
                return model
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NllmConfig:
        """Create config from dictionary (loaded from YAML)."""
        # Parse models - support both string and dict formats
        raw_models = data.get("models", [])
        models = []
        for item in raw_models:
            if isinstance(item, str):
                models.append(ModelConfig.from_string(item))
            elif isinstance(item, dict):
                models.append(ModelConfig.from_dict(item))
            else:
                raise ValueError(f"Invalid model configuration: {item}")

        return cls(
            models=models,
            parallel=data.get("defaults", {}).get("parallel", 4),
            timeout=data.get("defaults", {}).get("timeout", 120),
            retries=data.get("defaults", {}).get("retries", 0),
            stream=data.get("defaults", {}).get("stream", True),
            outdir=data.get("defaults", {}).get("outdir", "./nllm-runs"),
            costs=data.get("costs", {}),
        )

    def merge_cli_args(
        self,
        models: list[ModelConfig] | None = None,
        parallel: int | None = None,
        timeout: int | None = None,
        retries: int | None = None,
        stream: bool | None = None,
        outdir: str | None = None,
    ) -> NllmConfig:
        """Create new config with CLI arguments merged in."""
        return NllmConfig(
            models=models if models is not None else self.models,
            parallel=parallel if parallel is not None else self.parallel,
            timeout=timeout if timeout is not None else self.timeout,
            retries=retries if retries is not None else self.retries,
            stream=stream if stream is not None else self.stream,
            outdir=outdir if outdir is not None else self.outdir,
            costs=self.costs,
        )


@dataclass
class ExecutionContext:
    """Context for a nllm execution run."""

    config: NllmConfig
    llm_args: list[str]
    output_dir: Path
    manifest: RunManifest
    quiet: bool = False
    dry_run: bool = False
    raw_output: bool = False

    def get_model_output_paths(self, model: str) -> tuple[Path, Path]:
        """Get stdout and stderr output paths for a model."""
        raw_dir = self.output_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        return (
            raw_dir / f"{model}.stdout.txt",
            raw_dir / f"{model}.stderr.txt",
        )

    def get_results_dir(self) -> Path:
        """Get the results directory path."""
        results_dir = self.output_dir / "results"
        results_dir.mkdir(exist_ok=True)
        return results_dir
