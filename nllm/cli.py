"""Command-line interface for nllm."""

import sys

import typer
from rich.console import Console

from . import __version__
from .app import run
from .constants import (
    CLI_DESCRIPTION,
    CONFIG_HELP,
    DRY_RUN_HELP,
    MODEL_HELP,
    OUTDIR_HELP,
    PARALLEL_HELP,
    QUIET_HELP,
    RAW_HELP,
    RETRIES_HELP,
    STREAM_HELP,
    TIMEOUT_HELP,
)

# Help text for new model options flag
MODEL_OPTION_HELP = "Per-model options in format model:option1:option2:... (repeatable)"

console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"nllm {__version__}")
        raise typer.Exit()


def main(
    models: list[str] | None = typer.Option(None, "-m", "--model", help=MODEL_HELP),
    model_options: list[str] | None = typer.Option(None, "--model-option", help=MODEL_OPTION_HELP),
    config_path: str | None = typer.Option(None, "-c", "--config", help=CONFIG_HELP),
    outdir: str | None = typer.Option(None, "-o", "--outdir", help=OUTDIR_HELP),
    parallel: int | None = typer.Option(None, "--parallel", help=PARALLEL_HELP),
    timeout: int | None = typer.Option(None, "--timeout", help=TIMEOUT_HELP),
    retries: int | None = typer.Option(None, "--retries", help=RETRIES_HELP),
    stream: bool | None = typer.Option(None, "--stream/--no-stream", help=STREAM_HELP),
    raw: bool = typer.Option(False, "--raw", help=RAW_HELP),
    dry_run: bool = typer.Option(False, "--dry-run", help=DRY_RUN_HELP),
    quiet: bool = typer.Option(False, "-q", "--quiet", help=QUIET_HELP),
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
    llm_args: list[str] | None = typer.Argument(
        None, help="Arguments to pass to llm (everything after --)"
    ),
) -> None:
    """
    Multi-model fan-out wrapper for the `llm` CLI tool.

    Execute the same prompt across multiple AI models concurrently, with structured output
    and streaming console feedback. Supports all llm flags and options transparently.

    Examples:
      nllm -m gpt-4 -m claude-3-sonnet -- "Explain quantum computing"
      nllm --model-option gpt-4:-o:temperature:0.7 -- "Write a haiku"
      nllm -m gpt-4 --model-option gpt-4:--system:"You are concise" -- "Summarize quantum computing"
      nllm -c my-config.yaml -- "What is the capital of France?"
    """
    # Convert llm_args from None to empty list if needed
    if llm_args is None:
        llm_args = []

    # Run the main application
    try:
        results = run(
            cli_models=models,
            cli_model_options=model_options or [],
            config_path=config_path,
            outdir=outdir,
            parallel=parallel,
            timeout=timeout,
            retries=retries,
            stream=stream,
            raw=raw,
            dry_run=dry_run,
            quiet=quiet,
            llm_args=llm_args,
        )
        exit_code = results.exit_code

    except Exception as e:
        # Handle errors for CLI usage
        if not quiet:
            if "ConfigError" in str(type(e)):
                console.print(f"[red]Configuration error:[/red] {e}")
            elif "ExecutionError" in str(type(e)):
                console.print(f"[red]Execution error:[/red] {e}")
            elif "KeyboardInterrupt" in str(type(e)):
                console.print("\n[yellow]Interrupted by user[/yellow]")
            else:
                console.print(f"[red]Unexpected error:[/red] {e}")
                if not dry_run:  # Show traceback for debugging unless in dry run
                    import traceback

                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
        exit_code = 1

    sys.exit(exit_code)


def cli_main() -> None:
    """Entry point for the CLI application."""
    # Create the typer app
    app = typer.Typer(
        name="nllm",
        help=CLI_DESCRIPTION.strip(),
        add_completion=False,
        no_args_is_help=True,
        context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
    )

    # Add the main command
    app.command()(main)

    # Run the app
    app()


if __name__ == "__main__":
    cli_main()
