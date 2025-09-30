# Data Models and Schemas

## Overview

nllm uses strongly-typed data models throughout the system to ensure data integrity and provide clear API contracts. All models use Python dataclasses with comprehensive type hints.

## Core Data Models

### ModelResult

Represents the execution result from a single model.

```python
@dataclass
class ModelResult:
    model: str                                    # Model identifier (e.g., "gpt-4")
    status: Literal["ok", "error", "timeout"]     # Execution status
    duration_ms: int                             # Execution time in milliseconds
    exit_code: int                               # Process exit code
    text: str                                    # Raw text output from model
    meta: dict[str, Any] = field(default_factory=dict)  # Metadata (tokens, cost, etc.)
    command: list[str] = field(default_factory=list)    # Actual command executed
    stderr_tail: str = ""                        # Last few lines of stderr
    json: dict[str, Any] | list | None = None    # Extracted JSON (if found)
```

#### Status Values
- `"ok"`: Model executed successfully (exit code 0)
- `"error"`: Model failed with non-zero exit code
- `"timeout"`: Model execution exceeded timeout limit

#### JSON Field
The `json` field contains automatically extracted JSON from the model's text output:
- `dict`: For JSON objects `{...}`
- `list`: For JSON arrays `[...]`
- `None`: No valid JSON found

#### Meta Field Examples
```python
# Token usage information
meta = {
    "tokens_input": 123,
    "tokens_output": 456,
    "cost_estimated": 0.0123
}

# Error information
meta = {
    "error": True,
    "error_message": "Authentication failed"
}

# Timeout information
meta = {
    "timeout": True
}
```

### NllmResults

Contains the complete results from an nllm execution run.

```python
@dataclass
class NllmResults:
    results: list[ModelResult]                   # Individual model results
    manifest: RunManifest                        # Execution metadata
    success_count: int                          # Number of successful models
    total_count: int                           # Total number of models
    exit_code: int                             # Overall exit code (0 or 1)

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
```

### RunManifest

Captures metadata about the execution environment and configuration.

```python
@dataclass
class RunManifest:
    cli_args: list[str]                         # Original CLI arguments
    resolved_models: list[str]                  # Final list of model names
    timestamp: str                              # ISO format timestamp
    hostname: str                               # Execution hostname
    git_sha: str | None = None                  # Git commit SHA (if available)
    config_paths_used: list[str] = field(default_factory=list)  # Config files loaded
    llm_version: str | None = None              # Version of llm CLI tool
    os_info: str = field(default_factory=lambda: platform.platform())  # OS information
    working_directory: str = field(default_factory=lambda: str(Path.cwd()))  # Current directory
```

#### Factory Methods
```python
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
```

## Configuration Models

### ModelConfig

Represents a model with its associated configuration options.

```python
@dataclass
class ModelConfig:
    name: str                                   # Model identifier
    options: list[str] = field(default_factory=list)  # Per-model options

    @classmethod
    def from_string(cls, model_str: str) -> ModelConfig:
        """Create ModelConfig from a simple string."""
        return cls(name=model_str, options=[])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        """Create ModelConfig from dictionary."""
        if "name" not in data:
            raise ValueError("Model config must have 'name' field")
        return cls(name=data["name"], options=data.get("options", []))
```

#### Examples
```python
# Simple model
config1 = ModelConfig(name="gpt-4", options=[])

# Model with options
config2 = ModelConfig(
    name="claude-3-sonnet",
    options=["-o", "temperature", "0.2", "--system", "Be concise"]
)
```

### NllmConfig

Main configuration class containing all execution parameters.

```python
@dataclass
class NllmConfig:
    models: list[ModelConfig] = field(default_factory=list)  # Models to execute
    timeout: int | None = None                  # Per-model timeout (seconds, optional)
    retries: int = 0                           # Retry attempts for transient errors
    stream: bool = True                        # Enable streaming output
    outdir: str = "./nllm-runs"               # Base output directory
    costs: dict[str, dict[str, float]] = field(default_factory=dict)  # Cost estimates

    def get_model_names(self) -> list[str]:
        """Get list of model names."""
        return [model.name for model in self.models]

    def get_model_config(self, model_name: str) -> ModelConfig | None:
        """Get configuration for a specific model."""
        for model in self.models:
            if model.name == model_name:
                return model
        return None
```

#### Configuration Loading
```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> NllmConfig:
    """Create config from dictionary (loaded from YAML)."""
    # Supports both string and dict formats for models
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
        timeout=data.get("defaults", {}).get("timeout", None),
        retries=data.get("defaults", {}).get("retries", 0),
        stream=data.get("defaults", {}).get("stream", True),
        outdir=data.get("defaults", {}).get("outdir", "./nllm-runs"),
        costs=data.get("costs", {}),
    )
```

### ExecutionContext

Runtime context for an nllm execution, combining configuration with runtime parameters.

```python
@dataclass
class ExecutionContext:
    config: NllmConfig                          # Merged configuration
    llm_args: list[str]                        # Arguments to pass to llm
    output_dir: Path                           # Output directory for this run
    manifest: RunManifest                      # Execution metadata
    quiet: bool = False                        # Suppress console output
    dry_run: bool = False                      # Show commands without executing
    raw_output: bool = False                   # Save raw stdout/stderr files
    using_temp_dir: bool = False               # Whether using temporary directory

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
```

## JSON Schemas

### Manifest JSON Schema
```json
{
  "type": "object",
  "required": ["cli_args", "resolved_models", "timestamp", "hostname"],
  "properties": {
    "cli_args": {
      "type": "array",
      "items": {"type": "string"}
    },
    "resolved_models": {
      "type": "array",
      "items": {"type": "string"}
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "hostname": {"type": "string"},
    "git_sha": {
      "type": ["string", "null"],
      "pattern": "^[a-f0-9]{40}$"
    },
    "config_paths_used": {
      "type": "array",
      "items": {"type": "string"}
    },
    "llm_version": {
      "type": ["string", "null"]
    },
    "os_info": {"type": "string"},
    "working_directory": {"type": "string"}
  }
}
```

### Results JSONL Schema
Each line in `results.jsonl` follows this schema:

```json
{
  "type": "object",
  "required": ["model", "status", "duration_ms", "exit_code", "text"],
  "properties": {
    "model": {"type": "string"},
    "status": {
      "type": "string",
      "enum": ["ok", "error", "timeout"]
    },
    "duration_ms": {
      "type": "integer",
      "minimum": 0
    },
    "exit_code": {"type": "integer"},
    "text": {"type": "string"},
    "meta": {
      "type": "object",
      "properties": {
        "tokens_input": {"type": "integer", "minimum": 0},
        "tokens_output": {"type": "integer", "minimum": 0},
        "cost_estimated": {"type": "number", "minimum": 0},
        "error": {"type": "boolean"},
        "error_message": {"type": "string"},
        "timeout": {"type": "boolean"}
      }
    },
    "command": {
      "type": "array",
      "items": {"type": "string"}
    },
    "stderr_tail": {"type": "string"},
    "json": {
      "oneOf": [
        {"type": "object"},
        {"type": "array"},
        {"type": "null"}
      ]
    }
  }
}
```

### Configuration YAML Schema
```yaml
# Schema for .nllm-config.yaml
models:
  type: array
  items:
    oneOf:
      # Simple string format
      - type: string
      # Object format with options
      - type: object
        required: [name]
        properties:
          name:
            type: string
          options:
            type: array
            items:
              type: string

defaults:
  type: object
  properties:
    timeout:
      type: integer
      minimum: 1
    retries:
      type: integer
      minimum: 0
    stream:
      type: boolean
    outdir:
      type: string

costs:
  type: object
  patternProperties:
    ".*":  # Model name
      type: object
      properties:
        input_per_1k:
          type: number
          minimum: 0
        output_per_1k:
          type: number
          minimum: 0
```

## Serialization and Deserialization

### To Dictionary Conversion
All models provide `to_dict()` methods for JSON serialization:

```python
# ModelResult to dict
result_dict = model_result.to_dict()

# RunManifest to dict
manifest_dict = manifest.to_dict()
```

### JSON File Generation
```python
# Save manifest
manifest_path = output_dir / "manifest.json"
save_json_safely(manifest.to_dict(), manifest_path)

# Save results JSONL
results_path = output_dir / "results.jsonl"
with results_path.open("w", encoding="utf-8") as f:
    for result in results:
        f.write(json.dumps(result.to_dict()) + "\n")
```

## Validation and Error Handling

### Configuration Validation
```python
def validate_config(config: NllmConfig) -> None:
    """Validate configuration values."""
    if config.timeout < 1:
        raise ConfigError("timeout must be at least 1 second")

    if config.retries < 0:
        raise ConfigError("retries cannot be negative")

    if not config.outdir:
        raise ConfigError("outdir cannot be empty")
```

### Model Loading Validation
```python
# Validate model config dictionary
def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
    if "name" not in data:
        raise ValueError("Model config must have 'name' field")
    # ... rest of validation
```

## Type Safety

### Runtime Type Checking
While nllm uses static type hints, critical data transformations include runtime validation:

```python
# Ensure status is valid
if result.status not in ("ok", "error", "timeout"):
    raise ValueError(f"Invalid status: {result.status}")

# Validate JSON extraction result
if extracted_json is not None:
    if not isinstance(extracted_json, (dict, list)):
        extracted_json = None  # Reset to None if invalid type
```

### MyPy Compatibility
All models are fully compatible with MyPy static type checking:
- All fields have explicit type annotations
- Optional fields use `| None` syntax (Python 3.10+)
- Generic types specify their contents (`list[str]`, `dict[str, Any]`)

## Extension Points

### Custom Metadata
The `meta` field in `ModelResult` allows for extensible metadata:

```python
# Custom metadata extraction
def extract_custom_metadata(stderr: str) -> dict[str, Any]:
    meta = {}

    # Extract provider-specific information
    if "anthropic" in stderr.lower():
        meta["provider"] = "anthropic"
    elif "openai" in stderr.lower():
        meta["provider"] = "openai"

    return meta
```

### Future Model Extensions
The data model design supports future enhancements:

1. **Result Comparison**: Additional fields for model comparison
2. **Batch Processing**: Support for multiple prompts per model
3. **Caching**: Cache keys and metadata
4. **Analytics**: Enhanced usage tracking

## Best Practices

### Immutability
- Data models should be treated as immutable after creation
- Use `field(default_factory=...)` for mutable defaults
- Create new instances rather than modifying existing ones

### Error Handling
- Always validate external data when creating models
- Use descriptive error messages for validation failures
- Provide fallback values for optional fields

### JSON Compatibility
- All model data should be JSON-serializable
- Use `to_dict()` methods for consistent serialization
- Handle datetime objects with ISO format strings