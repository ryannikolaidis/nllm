"""Core execution engine for nllm."""

import asyncio
import json
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .constants import (
    DRY_RUN_PREFIX,
    MANIFEST_FILE,
    MODEL_PREFIX_FORMAT,
    RESULTS_JSONL_FILE,
    STATUS_ERROR,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
)
from .models import ExecutionContext, ModelConfig, ModelResult
from .utils import (
    ExecutionError,
    classify_error,
    construct_llm_command,
    extract_json_from_text,
    format_duration,
    redact_secrets_from_args,
    retry_with_backoff,
    sanitize_filename,
    save_json_safely,
    truncate_stderr,
)


class ModelExecutor:
    """Handles execution of a single model."""

    def __init__(
        self,
        model_config: ModelConfig,
        context: ExecutionContext,
        console: Console,
        suppress_streaming: bool = False,
    ):
        self.model_config = model_config
        self.context = context
        self.console = console
        self.suppress_streaming = suppress_streaming
        self.start_time: float | None = None
        self.end_time: float | None = None

    @property
    def model(self) -> str:
        """Get the model name for backward compatibility."""
        return self.model_config.name

    async def execute(self) -> ModelResult:
        """Execute the model and return results."""
        if self.context.dry_run:
            return self._create_dry_run_result()

        self.start_time = time.time()

        async def _run_with_retry():
            return await self._run_model()

        try:
            if self.context.config.retries > 0:
                result = await retry_with_backoff(
                    _run_with_retry,
                    max_retries=self.context.config.retries,
                    base_delay=1.0,
                )
            else:
                result = await _run_with_retry()

            self.end_time = time.time()
            # Type hint for pyright - we know this must be ModelResult based on flow
            assert isinstance(result, ModelResult)
            return result

        except TimeoutError:
            self.end_time = time.time()
            return self._create_timeout_result()
        except Exception as e:
            self.end_time = time.time()
            return self._create_error_result(str(e))

    def _create_dry_run_result(self) -> ModelResult:
        """Create a result for dry run mode."""
        command = construct_llm_command(
            self.model_config.name, self.context.llm_args, self.model_config.options
        )
        command_str = " ".join(redact_secrets_from_args(command))

        if not self.context.quiet:
            self.console.print(f"{DRY_RUN_PREFIX} [{self.model}] {command_str}")

        return ModelResult(
            model=self.model,
            status="ok",
            duration_ms=0,
            exit_code=0,
            text=f"DRY RUN: {command_str}",
            command=command,
            meta={"dry_run": True},
        )

    async def _run_model(self) -> ModelResult:
        """Run the actual model execution."""
        command = construct_llm_command(
            self.model_config.name, self.context.llm_args, self.model_config.options
        )

        # Create process
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
            )
        except FileNotFoundError:
            raise ExecutionError("llm command not found")

        # Set up output files if raw output is requested
        stdout_file = None
        stderr_file = None
        if self.context.raw_output:
            stdout_path, stderr_path = self.context.get_model_output_paths(self.model)
            stdout_file = stdout_path.open("w", encoding="utf-8")
            stderr_file = stderr_path.open("w", encoding="utf-8")

        try:
            # Run with timeout (if specified)
            if self.context.config.timeout is not None:
                stdout_data, stderr_data = await asyncio.wait_for(
                    self._stream_output(process, stdout_file, stderr_file),
                    timeout=self.context.config.timeout,
                )
            else:
                # No timeout - run indefinitely
                stdout_data, stderr_data = await self._stream_output(
                    process, stdout_file, stderr_file
                )

            # Wait for process to complete
            exit_code = await process.wait()

        except TimeoutError:
            # Kill the process
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
            raise TimeoutError()

        finally:
            if stdout_file:
                stdout_file.close()
            if stderr_file:
                stderr_file.close()

        # Create result
        duration_ms = int((self.end_time or time.time()) - (self.start_time or 0)) * 1000

        if exit_code == 0:
            # Extract JSON from the output text
            extracted_json = extract_json_from_text(stdout_data)

            return ModelResult(
                model=self.model,
                status="ok",
                duration_ms=duration_ms,
                exit_code=exit_code,
                text=stdout_data,
                command=command,
                stderr_tail=truncate_stderr(stderr_data, 5),
                meta=self._extract_metadata(stdout_data, stderr_data),
                json=extracted_json,
            )
        else:
            # Check if error is retryable
            is_retryable = classify_error(stderr_data)
            if is_retryable:
                raise ExecutionError(f"Retryable error: {truncate_stderr(stderr_data, 3)}")

            # Try to extract JSON even from error responses
            extracted_json = extract_json_from_text(stdout_data)

            return ModelResult(
                model=self.model,
                status="error",
                duration_ms=duration_ms,
                exit_code=exit_code,
                text=stdout_data,
                command=command,
                stderr_tail=truncate_stderr(stderr_data, 10),
                meta={"error": True},
                json=extracted_json,
            )

    async def _stream_output(
        self,
        process: asyncio.subprocess.Process,
        stdout_file,
        stderr_file,
    ) -> tuple[str, str]:
        """Stream output from process, optionally to console and files."""
        stdout_lines = []
        stderr_lines = []

        async def read_stream(stream, lines_list, file_handle, is_stderr=False):
            while True:
                line = await stream.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace")
                lines_list.append(line_str)

                # Write to file if requested
                if file_handle:
                    file_handle.write(line_str)
                    file_handle.flush()

                # Stream to console if not quiet and not suppressed (for live progress)
                if (
                    self.context.config.stream
                    and not self.context.quiet
                    and not self.suppress_streaming
                ):
                    prefix = MODEL_PREFIX_FORMAT.format(model=self.model)
                    if is_stderr:
                        self.console.print(f"{prefix} [red]{line_str.rstrip()}[/red]")
                    else:
                        self.console.print(f"{prefix} {line_str.rstrip()}")

        # Read both streams concurrently
        await asyncio.gather(
            read_stream(process.stdout, stdout_lines, stdout_file, False),
            read_stream(process.stderr, stderr_lines, stderr_file, True),
        )

        return "".join(stdout_lines), "".join(stderr_lines)

    def _create_timeout_result(self) -> ModelResult:
        """Create result for timeout case."""
        duration_ms = int((self.end_time or time.time()) - (self.start_time or 0)) * 1000
        command = construct_llm_command(
            self.model_config.name, self.context.llm_args, self.model_config.options
        )

        return ModelResult(
            model=self.model,
            status="timeout",
            duration_ms=duration_ms,
            exit_code=-1,
            text="",
            command=command,
            stderr_tail=f"Timeout after {self.context.config.timeout or 'unknown'} seconds",
            meta={"timeout": True},
        )

    def _create_error_result(self, error_message: str) -> ModelResult:
        """Create result for error case."""
        duration_ms = int((self.end_time or time.time()) - (self.start_time or 0)) * 1000
        command = construct_llm_command(
            self.model_config.name, self.context.llm_args, self.model_config.options
        )

        return ModelResult(
            model=self.model,
            status="error",
            duration_ms=duration_ms,
            exit_code=-1,
            text="",
            command=command,
            stderr_tail=truncate_stderr(error_message, 5),
            meta={"error": True, "error_message": error_message},
        )

    def _extract_metadata(self, stdout: str, stderr: str) -> dict:
        """Extract metadata from llm output (tokens, cost, etc.)."""
        import re

        meta = {}

        # Try to parse token usage from stderr (common llm pattern)
        stderr_lines = stderr.split("\n")
        for line in stderr_lines:
            line = line.strip().lower()
            if "tokens" in line:
                # Look for patterns like "Input tokens: 123, Output tokens: 456"
                input_match = re.search(r"input.*?(\d+)", line)
                output_match = re.search(r"output.*?(\d+)", line)

                if input_match:
                    meta["tokens_input"] = int(input_match.group(1))
                if output_match:
                    meta["tokens_output"] = int(output_match.group(1))

            if "cost" in line or "$" in line:
                # Look for cost information
                cost_match = re.search(r"\$?(\d+\.?\d*)", line)
                if cost_match:
                    meta["cost_estimated"] = float(cost_match.group(1))

        return meta


class NllmExecutor:
    """Main executor that orchestrates multiple model runs."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.console = Console()
        self.results: list[ModelResult] = []
        self.model_status: dict[str, dict] = {}  # Track model status for live updates

    async def execute_all(self) -> list[ModelResult]:
        """Execute all models and return results."""
        models = self.context.config.models

        if not models:
            raise ExecutionError("No models specified")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(4)  # Default parallel execution

        async def run_single_model(model_config: ModelConfig) -> ModelResult:
            async with semaphore:
                executor = ModelExecutor(model_config, self.context, self.console)
                return await executor.execute()

        # Initialize status for all models
        for model_config in models:
            self.model_status[model_config.name] = {
                "status": "running",
                "duration": "",
                "result_file": "",
            }

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(4)  # Default parallel execution

        # Execute all models with live progress
        if not self.context.quiet and not self.context.dry_run:
            # Use a lock to prevent concurrent updates
            update_lock = asyncio.Lock()
            with Live(self._create_progress_table(), refresh_per_second=1) as live:
                tasks = [
                    self._run_single_model_with_progress(model, live, semaphore, update_lock)
                    for model in models
                ]
                self.results = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            tasks = [run_single_model(model) for model in models]
            self.results = await asyncio.gather(*tasks, return_exceptions=False)

        # Save artifacts
        if not self.context.dry_run:
            await self._save_artifacts()

        return self.results

    def _create_progress_table(self) -> Table:
        """Create live progress table."""
        table = Table(title="Model Execution Progress", show_lines=True)
        table.add_column("Model", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center", min_width=20)
        table.add_column("Duration", justify="right", min_width=10)

        for model, status in self.model_status.items():
            if status["status"] == "running":
                status_text = Text(f"{STATUS_RUNNING} Running...", style="yellow")
            elif status["status"] == "completed":
                status_text = Text(f"{STATUS_SUCCESS} Completed", style="green")
            elif status["status"] == "timeout":
                status_text = Text(f"{STATUS_TIMEOUT} Timeout", style="red")
            else:
                status_text = Text(f"{STATUS_ERROR} Error", style="red")

            table.add_row(model, status_text, status["duration"])

        return table

    async def _run_single_model_with_progress(
        self, model_config: ModelConfig, live, semaphore, update_lock
    ) -> ModelResult:
        """Run a single model and update progress table."""
        async with semaphore:
            executor = ModelExecutor(
                model_config, self.context, self.console, suppress_streaming=True
            )
            result = await executor.execute()

            # Update status based on result (with lock to prevent concurrent updates)
            async with update_lock:
                if result.status == "ok":
                    self.model_status[model_config.name] = {
                        "status": "completed",
                        "duration": format_duration(result.duration_ms),
                        "result_file": f"results/{sanitize_filename(model_config.name)}.json",
                    }
                elif result.status == "timeout":
                    self.model_status[model_config.name] = {
                        "status": "timeout",
                        "duration": format_duration(result.duration_ms),
                        "result_file": "",
                    }
                else:
                    self.model_status[model_config.name] = {
                        "status": "error",
                        "duration": format_duration(result.duration_ms),
                        "result_file": "",
                    }

                # Update the live display
                live.update(self._create_progress_table())

            return result

    async def _save_artifacts(self) -> None:
        """Save all output artifacts."""
        # Save manifest
        manifest_path = self.context.output_dir / MANIFEST_FILE
        save_json_safely(self.context.manifest.to_dict(), manifest_path)

        # Save results JSONL
        results_path = self.context.output_dir / RESULTS_JSONL_FILE
        with results_path.open("w", encoding="utf-8") as f:
            for result in self.results:
                f.write(json.dumps(result.to_dict()) + "\n")

        # Save individual result files
        results_dir = self.context.get_results_dir()
        for result in self.results:
            result_path = results_dir / f"{sanitize_filename(result.model)}.json"
            save_json_safely(result.to_dict(), result_path)

    def print_summary(self) -> None:
        """Print execution summary."""
        if self.context.quiet:
            return

        success_count = sum(1 for r in self.results if r.status == "ok")
        total_count = len(self.results)

        if success_count == total_count:
            message = f"✓ All {total_count} models completed successfully"
            style = "green"
        else:
            message = f"⚠ {success_count} of {total_count} models completed successfully"
            style = "yellow"

        if not self.context.dry_run and not self.context.using_temp_dir:
            artifacts_msg = f"Artifacts saved to: {self.context.output_dir}"
            panel_content = f"{message}\n{artifacts_msg}"
        else:
            panel_content = message

        panel = Panel(panel_content, title="Summary", style=style)
        self.console.print(panel)

    def get_exit_code(self) -> int:
        """Get appropriate exit code based on results."""
        if self.context.dry_run:
            return 0

        # Return 1 if any model failed or timed out
        for result in self.results:
            if result.status in ("error", "timeout"):
                return 1

        return 0
