# nllm

Multi-model fan-out wrapper for the `llm` CLI tool. Execute the same prompt across multiple AI models concurrently, with structured output and streaming console feedback.

## Features

- **Multi-model execution** - Run prompts across multiple AI models simultaneously
- **Streaming output** - Real-time console feedback with model-tagged output and immediate result writing
- **Flexible configuration** - CLI arguments or YAML config files with per-model options
- **JSON extraction** - Automatically detect and parse JSON responses from model outputs
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

# With per-model options
nllm -m gpt-4 --model-option gpt-4:-o:temperature:0.2 -- "Generate code"

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

    # Access parsed JSON if available
    if result.json:
        print(f"Parsed JSON: {result.json}")

# With configuration options and per-model options
results = nllm.run(
    cli_models=["gpt-4o-mini", "gemini-pro"],
    cli_model_options=[
        "gpt-4o-mini:-o:temperature:0.1",
        "gemini-pro:--system:You are concise"
    ],
    outdir="./my-results",
    timeout=60,
    dry_run=True,
    llm_args=["-t", "0.7", "Write a haiku about programming"]
)

# Access individual model results
gpt4_result = results.get_result("gpt-4o-mini")
if gpt4_result and gpt4_result.status == "ok":
    print(f"GPT-4 response: {gpt4_result.text}")
    # Check for extracted JSON
    if gpt4_result.json:
        print(f"JSON data: {gpt4_result.json}")

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
- `results`: List of individual model results (with `json` field for parsed JSON)
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
| `--model-option` | Per-model options in format `model:option1:option2:...` (repeatable) |
| `-c, --config` | Path to config file (default: `./.nllm-config.yaml` or `~/.nllm/config.yaml`) |
| `-o, --outdir` | Output directory for results (default: `./nllm-runs/<timestamp>`) |
| `--timeout SECONDS` | Per-model timeout in seconds (default: no timeout) |
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

#### Per-Model Options

```bash
# Set different temperatures for different models
nllm -m gpt-4 -m claude-3-sonnet \\
  --model-option gpt-4:-o:temperature:0.2 \\
  --model-option claude-3-sonnet:-o:temperature:0.8 \\
  -- "Write creative content"

# Per-model system prompts
nllm -m gpt-4 -m claude-3-sonnet \\
  --model-option gpt-4:--system:"You are precise and analytical" \\
  --model-option claude-3-sonnet:--system:"You are creative and conversational" \\
  -- "Explain machine learning"
```

#### Using Configuration Files

Create `.nllm-config.yaml`:

```yaml
# Support both simple strings and per-model options
models:
  - "gpt-4"  # Simple format
  - name: "claude-3-sonnet"  # With per-model options
    options: ["-o", "temperature", "0.2", "--system", "You are concise"]
  - name: "gemini-pro"
    options: ["-o", "temperature", "0.8"]

defaults:
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

## JSON Extraction

nllm automatically detects and extracts JSON from model responses using multiple strategies:

1. **Direct JSON parsing** - Raw JSON objects or arrays
2. **Markdown code blocks** - `\`\`\`json` or `\`\`\`` blocks containing JSON
3. **Embedded JSON** - JSON objects/arrays found within larger text

The extracted JSON is available in the `json` field of each `ModelResult`:

```python
result = results.get_result("gpt-4")
if result.json:
    # JSON was successfully extracted and parsed
    data = result.json  # dict, list, or None
```

### JSON Examples

Models can return JSON in various formats, all automatically detected:

```json
{"status": "success", "data": [1, 2, 3]}
```

```markdown
Here's the data you requested:
```json
{
  "results": ["item1", "item2"],
  "count": 2
}
```
```

```text
The analysis shows: {"confidence": 0.95, "prediction": "positive"}
```

## Output Structure

nllm creates a timestamped directory immediately when execution starts and writes results incrementally as each model completes. This provides immediate feedback and allows accessing partial results during long-running executions:

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

Each line in `results.jsonl` and individual result files:

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
  "stderr_tail": "Usage: 30 tokens",
  "json": null
}
```

### Streaming Result Writing

nllm writes results incrementally for immediate feedback:

1. **Immediate setup**: Output directory and command information are written as soon as execution starts
2. **Per-model completion**: Each model's results are saved immediately when that model finishes
3. **Visual feedback**: Console shows ✅/❌ completion indicators as models finish
4. **Parallel access**: Results can be accessed while other models are still running

This allows monitoring progress and accessing results during long-running multi-model executions.

With JSON extraction:

```json
{
  "model": "gpt-4",
  "status": "ok",
  "duration_ms": 1834,
  "exit_code": 0,
  "text": "```json\\n{\\\"status\\\": \\\"success\\\", \\\"data\\\": [1, 2, 3]}\\n```",
  "meta": {},
  "command": ["llm", "-m", "gpt-4", "Return JSON"],
  "stderr_tail": "",
  "json": {
    "status": "success",
    "data": [1, 2, 3]
  }
}
```

## Configuration

### Config File Precedence

1. `--config <path>` (if provided)
2. `./.nllm-config.yaml` (current directory)
3. `~/.nllm/config.yaml` (home directory)

### Config File Schema

```yaml
# List of models - supports both simple and advanced formats
models:
  - "gpt-4"  # Simple string format
  - name: "claude-3-sonnet"  # Object format with options
    options: ["-o", "temperature", "0.2", "--system", "Be concise"]
  - name: "gemini-pro"
    options: ["-o", "temperature", "0.8"]

# Default behavior settings
defaults:
  # timeout: 300  # Optional: per-model timeout in seconds (default: no timeout)      # Per-model timeout (seconds)
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
  - name: "claude-3-sonnet"
    options: ["--system", "You are helpful"]

defaults:
  timeout: 180  # Set timeout when needed
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

nllm classifies errors as either **transient** (retryable) or **permanent**:

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
# Increase timeout
nllm --timeout 300 -m gpt-4 -- "Complex task"
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
│   ├── __init__.py       # Version info and exports
│   ├── cli.py           # CLI interface (Typer)
│   ├── app.py           # Main application logic and Python API
│   ├── core.py          # Execution engine (async subprocess management)
│   ├── config.py        # Configuration loading and validation
│   ├── models.py        # Data models (Pydantic-style dataclasses)
│   ├── utils.py         # Utilities (JSON extraction, error handling)
│   └── constants.py     # Constants and defaults
├── tests/               # Comprehensive test suite
├── docs/                # Documentation
│   └── design/          # Architecture and design documents
└── pyproject.toml       # Project configuration
```

### Testing

The test suite includes:
- Unit tests for all modules
- Integration tests with mocked `llm` subprocess
- Configuration loading and validation tests
- JSON extraction tests with various formats
- Error handling and edge case tests
- Per-model options functionality

```bash
# Run specific test files
uv run pytest tests/test_config.py -v

# Run with coverage reporting
make test-cov

# Test specific functionality
uv run pytest tests/test_utils.py::TestExtractJsonFromText -v
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