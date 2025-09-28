# nllm

Multi-model fan-out wrapper for the `llm` CLI tool. Execute the same prompt across multiple AI models concurrently, with structured output and streaming console feedback.

## Features

- **Multi-model execution** - Run prompts across multiple AI models simultaneously
- **Streaming output** - Real-time console feedback with model-tagged output
- **Flexible configuration** - CLI arguments or YAML config files
- **Structured artifacts** - JSON/JSONL output with complete run metadata
- **Robust error handling** - Per-model timeouts, retries, and failure classification
- **Pass-through compatibility** - Transparently forwards all `llm` flags and options
- **Rich terminal output** - Progress indicators and formatted summaries
- **Dry-run mode** - Preview commands without execution
- **Modern Python tooling** - Built with uv, ruff, black, pyright, pytest

## Prerequisites

This tool requires the [`llm` CLI tool](https://github.com/simonw/llm) to be installed and configured:

```bash
# Install llm
pipx install llm

# Configure your API keys (example)
llm keys set openai sk-your-api-key-here
llm keys set anthropic your-anthropic-key-here

# Test llm is working
llm "Hello world"
```

## Installation

### Global Installation (Recommended)

```bash
# Clone and install globally with pipx
git clone https://github.com/ryannikolaidis/nllm.git
cd nllm
make install-package
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/ryannikolaidis/nllm.git
cd nllm

# Install dependencies
make install-dev
```

### Uninstall

```bash
make uninstall-package
# Or: pipx uninstall nllm
```

## Quick Start

```bash
# Run a prompt on multiple models
nllm -m gpt-4 -m claude-3-sonnet -- "Explain quantum computing in simple terms"

# Use a config file with predefined models
nllm -- "What is the capital of France?"

# Dry run to see what commands would be executed
nllm -m gpt-4 --dry-run -- "Hello world"

# Quiet mode for scripting
nllm -q -m gpt-4 -- "Generate a UUID"
```

## Usage

### Python API

You can use nllm directly in Python scripts:

```python
import nllm

# Simple usage
results = nllm.run(
    cli_models=["gpt-4", "claude-3-sonnet"],
    llm_args=["Explain quantum computing"]
)

# Check results
print(f"Success: {results.success}")
print(f"Completed: {results.success_count}/{results.total_count} models")
for result in results.results:
    print(f"{result.model}: {result.text[:100]}...")

# With configuration options
results = nllm.run(
    cli_models=["gpt-4o-mini", "gemini-pro"],
    outdir="./my-results",  # Save files instead of using temp
    parallel=2,
    timeout=60,
    dry_run=True,
    llm_args=["-t", "0.7", "Write a haiku about programming"]
)

# Access individual model results
gpt4_result = results.get_result("gpt-4o-mini")
if gpt4_result and gpt4_result.status == "ok":
    print(f"GPT-4 response: {gpt4_result.text}")

# Error handling - exceptions are raised for configuration errors
try:
    results = nllm.run(
        cli_models=["nonexistent-model"],
        llm_args=["test"]
    )
except nllm.ConfigError as e:
    print(f"Configuration error: {e}")
```

The `run()` function returns an `NllmResults` object with:
- `results`: List of individual model results
- `success`: Boolean - True if all models completed successfully
- `exit_code`: Integer (0 for success, 1 for any failures)
- `success_count`/`total_count`: Counters
- `get_result(model)`: Get result for specific model
- `successful_models`/`failed_models`: Lists of model names

### CLI Usage

#### Basic Command Structure

```bash
nllm [OPTIONS] -- [PROMPT and/or llm passthrough args]
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-m, --model` | Model to use (repeatable). Overrides config file models |
| `-c, --config` | Path to config file (default: `./.nllm-config.yaml` or `~/.nllm/config.yaml`) |
| `-o, --outdir` | Output directory for results (default: `./nllm-runs/<timestamp>`) |
| `--parallel N` | Maximum concurrent models (default: 4) |
| `--timeout SECONDS` | Per-model timeout in seconds (default: 120) |
| `--retries N` | Per-model retries for transient errors (default: 0) |
| `--stream/--no-stream` | Stream model outputs to console (default: `--stream`) |
| `--raw` | Save raw stdout/stderr files in addition to parsed content |
| `--dry-run` | Show resolved commands without executing |
| `-q, --quiet` | Reduce console output (errors still shown) |
| `--version` | Show version and exit |

### Examples

#### Using CLI Model Selection

```bash
# Single model
nllm -m gpt-4 -- "Write a haiku about programming"

# Multiple models
nllm -m gpt-4 -m claude-3-sonnet -m gemini-pro -- "Explain recursion"

# With llm options
nllm -m gpt-4 -- -t 0.2 --system "You are helpful" "Plan my day"
```

#### Using Configuration Files

Create `.nllm-config.yaml`:

```yaml
models:
  - "gpt-4"
  - "claude-3-sonnet"
  - "gemini-pro"

defaults:
  parallel: 3
  timeout: 120
  retries: 1
  stream: true
  outdir: "./my-nllm-runs"

# Optional: Cost tracking (estimates)
costs:
  gpt-4:
    input_per_1k: 0.03
    output_per_1k: 0.06
  claude-3-sonnet:
    input_per_1k: 0.003
    output_per_1k: 0.015
```

Then run without specifying models:

```bash
nllm -- "Compare different sorting algorithms"
```

#### Advanced Usage

```bash
# Custom output directory and timeout
nllm -m gpt-4 -o ./my-results --timeout 300 -- "Long analysis task"

# Non-streaming mode with retries
nllm --no-stream --retries 2 -m gpt-4 -- "Flaky network request"

# Save raw outputs for debugging
nllm --raw -m gpt-4 -- "Debug this code: print('hello')"

# Quiet mode for scripts
nllm -q -m gpt-4 -- "Generate random number" | jq '.results[0].text'
```

## Output Structure

Each nllm run creates a timestamped directory with structured output:

```
./nllm-runs/2023-01-01_12-30-45/
├── manifest.json          # Run metadata and configuration
├── results.jsonl          # One JSON result per line (per model)
├── raw/                   # Raw stdout/stderr (if --raw used)
│   ├── gpt-4.stdout.txt
│   ├── gpt-4.stderr.txt
│   └── ...
└── results/               # Individual JSON result files
    ├── gpt-4.json
    ├── claude-3-sonnet.json
    └── ...
```

### Manifest Format

```json
{
  "cli_args": ["nllm", "-m", "gpt-4", "--", "Hello world"],
  "resolved_models": ["gpt-4"],
  "timestamp": "2023-01-01T12:30:45.123456",
  "hostname": "my-machine",
  "git_sha": "abc123def456",
  "config_paths_used": ["./.nllm-config.yaml"],
  "llm_version": "0.10.0",
  "os_info": "Darwin-22.0.0",
  "working_directory": "/path/to/work"
}
```

### Results Format

Each line in `results.jsonl`:

```json
{
  "model": "gpt-4",
  "status": "ok",
  "duration_ms": 2341,
  "exit_code": 0,
  "text": "Hello! How can I help you today?",
  "meta": {
    "tokens_input": 10,
    "tokens_output": 20,
    "cost_estimated": 0.0012
  },
  "command": ["llm", "-m", "gpt-4", "Hello world"],
  "stderr_tail": "Usage: 30 tokens"
}
```

## Configuration

### Config File Precedence

1. `--config <path>` (if provided)
2. `./.nllm-config.yaml` (current directory)
3. `~/.nllm/config.yaml` (home directory)

### Config File Schema

```yaml
# List of models to use by default
models:
  - "gpt-4"
  - "claude-3-sonnet"
  - "gemini-pro"

# Default behavior settings
defaults:
  parallel: 4       # Max concurrent models
  timeout: 120      # Per-model timeout (seconds)
  retries: 0        # Per-model retries for transient errors
  stream: true      # Stream outputs to console
  outdir: "./nllm-runs"  # Base output directory

# Optional: Cost estimates per model
costs:
  gpt-4:
    input_per_1k: 0.03
    output_per_1k: 0.06
  claude-3-sonnet:
    input_per_1k: 0.003
    output_per_1k: 0.015
```

### Creating Config Files

```bash
# Generate example config in current directory
cat > .nllm-config.yaml << 'EOF'
models:
  - "gpt-4"
  - "claude-3-sonnet"

defaults:
  parallel: 3
  timeout: 180
  retries: 1
EOF

# Or create in home directory
mkdir -p ~/.nllm
cat > ~/.nllm/config.yaml << 'EOF'
models:
  - "gpt-4"
  - "claude-3-sonnet"
  - "gemini-pro"
EOF
```

## Error Handling

Prompter classifies errors as either **transient** (retryable) or **permanent**:

### Transient Errors (Will Retry)
- Connection timeouts
- Rate limiting (5xx errors, "too many requests")
- Service unavailable, gateway timeouts
- Network connectivity issues

### Permanent Errors (Will Not Retry)
- Invalid model names
- Authentication failures (missing/invalid API keys)
- Bad request format (4xx errors)
- Unauthorized access

### Exit Codes
- `0` - All models completed successfully
- `1` - One or more models failed or timed out

## Troubleshooting

### Common Issues

**"llm command not found"**
```bash
# Install llm first
pipx install llm
```

**"No models specified"**
```bash
# Either use -m flag or create config file
nllm -m gpt-4 -- "Hello"
# OR create .nllm-config.yaml with models list
```

**"Authentication failed"**
```bash
# Configure API keys for your models
llm keys set openai your-key-here
llm keys set anthropic your-key-here
```

**Models timing out**
```bash
# Increase timeout or reduce concurrency
nllm --timeout 300 --parallel 2 -m gpt-4 -- "Complex task"
```

### Debug Mode

```bash
# Use dry-run to see exact commands
nllm --dry-run -m gpt-4 -- "Test prompt"

# Use raw output for debugging
nllm --raw -m gpt-4 -- "Debug this"
# Check raw/ directory for full stdout/stderr
```

## Development

### Setup

```bash
# Clone and install for development
git clone https://github.com/ryannikolaidis/nllm.git
cd nllm
make install-dev

# Install pre-commit hooks
uv run pre-commit install
```

### Common Commands

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run linting
make lint

# Fix formatting and linting issues
make tidy

# Run all checks (linting + type checking)
make check

# Bump version
make version-dev
```

### Project Structure

```
nllm/
├── nllm/
│   ├── __init__.py       # Version info
│   ├── cli.py           # CLI interface
│   ├── app.py           # Main application logic
│   ├── core.py          # Execution engine
│   ├── config.py        # Configuration management
│   ├── models.py        # Data models
│   ├── utils.py         # Utilities and error handling
│   └── constants.py     # Constants and defaults
├── tests/               # Test suite
├── docs/                # Documentation
└── pyproject.toml       # Project configuration
```

### Testing

The test suite includes:
- Unit tests for all modules
- Integration tests with mocked `llm` subprocess
- Configuration loading and validation tests
- Error handling and edge case tests

```bash
# Run specific test files
uv run pytest tests/test_config.py -v

# Run with coverage reporting
make test-cov
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `make tidy && make check` to ensure code quality
5. Submit a pull request

## Changelog

See the design documents in `docs/design/` for implementation details and architectural decisions.
