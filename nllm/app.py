"""Application module for nllm."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .config import load_config, merge_cli_config, validate_config
from .constants import ERROR_LLM_NOT_FOUND, ERROR_NO_MODELS
from .core import NllmExecutor
from .models import ExecutionContext, NllmResults, RunManifest
from .utils import (
    ConfigError,
    ExecutionError,
    NllmError,
    check_llm_available,
    create_timestamped_dir,
    get_git_sha,
)


def run(
    cli_models: list[str] | None = None,
    cli_model_options: list[str] | None = None,
    config_path: str | None = None,
    outdir: str | None = None,
    timeout: int | None = None,
    retries: int | None = None,
    stream: bool | None = None,
    raw: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    llm_args: list[str] | None = None,
) -> NllmResults:
    """Main entry point for nllm application.

    Returns:
        NllmResults containing execution results and metadata
    """
    if llm_args is None:
        llm_args = []
    if cli_model_options is None:
        cli_model_options = []

    try:
        # Load configuration
        config, config_files_used = load_config(config_path)

        # Merge CLI arguments (this resolves models with per-model options)
        config = merge_cli_config(
            config,
            cli_models=cli_models,
            cli_model_options=cli_model_options,
            cli_timeout=timeout,
            cli_retries=retries,
            cli_stream=stream,
            cli_outdir=outdir,
        )

        # Validate configuration
        validate_config(config)

        # Check we have models
        if not config.models:
            raise ConfigError(ERROR_NO_MODELS)

        # Check llm availability (unless dry run)
        if not dry_run:
            llm_available, llm_version = check_llm_available()
            if not llm_available:
                raise ExecutionError(ERROR_LLM_NOT_FOUND)
        else:
            llm_version = None

        # Create output directory
        temp_dir_cleanup = None
        if not dry_run:
            if outdir is not None:
                # Use CLI-specified output directory
                output_dir = create_timestamped_dir(outdir)
            elif config.outdir:
                # Use config-specified output directory
                output_dir = create_timestamped_dir(config.outdir)
            else:
                # Use temporary directory that will be cleaned up
                temp_dir_cleanup = tempfile.TemporaryDirectory()
                output_dir = Path(temp_dir_cleanup.name)
        else:
            output_dir = Path("/tmp")  # Dummy path for dry runs

        # Create manifest
        git_sha = get_git_sha() if not dry_run else None
        manifest = RunManifest.create(
            cli_args=_build_cli_args(
                cli_models,
                cli_model_options,
                config_path,
                outdir,
                timeout,
                retries,
                stream,
                raw,
                dry_run,
                quiet,
                llm_args,
            ),
            resolved_models=config.get_model_names(),
            config_paths_used=config_files_used,
            git_sha=git_sha,
            llm_version=llm_version,
        )

        try:
            # Create execution context
            context = ExecutionContext(
                config=config,
                llm_args=llm_args,
                output_dir=output_dir,
                manifest=manifest,
                quiet=quiet,
                dry_run=dry_run,
                raw_output=raw,
                using_temp_dir=temp_dir_cleanup is not None,
            )

            # Execute
            executor = NllmExecutor(context)
            asyncio.run(executor.execute_all())

            # Print summary unless quiet
            if not quiet:
                executor.print_summary()

            exit_code = executor.get_exit_code()

            # Always return results
            success_count = sum(1 for r in executor.results if r.status == "ok")
            result = NllmResults(
                results=executor.results,
                manifest=manifest,
                success_count=success_count,
                total_count=len(executor.results),
                exit_code=exit_code,
            )
            return result

        finally:
            # Clean up temporary directory if we created one
            if temp_dir_cleanup:
                temp_dir_cleanup.cleanup()

    except (ConfigError, ExecutionError, NllmError, KeyboardInterrupt):
        # For these errors, always raise - let the caller handle them
        # CLI will catch them and exit appropriately
        raise
    except Exception:
        # For unexpected errors, also raise
        raise


def _build_cli_args(
    cli_models: list[str] | None,
    cli_model_options: list[str] | None,
    config_path: str | None,
    outdir: str | None,
    timeout: int | None,
    retries: int | None,
    stream: bool | None,
    raw: bool,
    dry_run: bool,
    quiet: bool,
    llm_args: list[str],
) -> list[str]:
    """Reconstruct the CLI arguments for the manifest."""
    args = ["nllm"]

    if cli_models:
        for model in cli_models:
            args.extend(["-m", model])

    if cli_model_options:
        for option in cli_model_options:
            args.extend(["--model-option", option])

    if config_path:
        args.extend(["-c", config_path])

    if outdir:
        args.extend(["-o", outdir])


    if timeout is not None:
        args.extend(["--timeout", str(timeout)])

    if retries is not None:
        args.extend(["--retries", str(retries)])

    if stream is not None:
        if stream:
            args.append("--stream")
        else:
            args.append("--no-stream")

    if raw:
        args.append("--raw")

    if dry_run:
        args.append("--dry-run")

    if quiet:
        args.extend(["-q"])

    if llm_args:
        args.append("--")
        args.extend(llm_args)

    return args
