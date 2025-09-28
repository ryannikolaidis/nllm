# Implementation Plan for Multi-Model Fan-Out Wrapper

## Overview
Transform the existing `prompter` CLI from a simple greeting app into a multi-model fan-out wrapper for the `llm` CLI tool, according to the design document specifications in `000-design.md`.

## Core Implementation Tasks

### 1. Dependencies & Configuration
- Add PyYAML dependency for config file handling
- Add `click` or update `typer` usage for CLI argument parsing
- Implement config file resolution system (precedence: `--config` > `./.prompter-config.yaml` > `~/.prompter/config.yaml`)

### 2. CLI Interface Overhaul
- Replace existing commands (`hello`, `info`, `config`) with the main prompter command
- Implement argument parsing for:
  - `-m/--model` (repeatable)
  - `-c/--config`, `-o/--outdir`, `--parallel`, `--timeout`, `--retries`
  - `--stream/--no-stream`, `--raw`, `--dry-run`, `-q/--quiet`
  - Everything after `--` passes through to `llm`

### 3. Core Execution Engine
- Implement async subprocess execution using `asyncio.create_subprocess_exec`
- Add concurrency control via `asyncio.Semaphore`
- Implement per-model timeout and retry logic with exponential backoff
- Build command construction logic that forwards `llm` arguments correctly

### 4. Output & Streaming
- Implement real-time streaming with `[model]` prefixed output
- Create structured output directory with timestamped runs
- Generate `manifest.json`, `results.jsonl`, and per-model artifacts
- Add quiet mode and buffered output options

### 5. Configuration System
- Implement YAML config parsing with schema validation
- Add model list resolution with CLI override capability
- Implement defaults merging (config → CLI args → hardcoded defaults)

### 6. Error Handling & Reporting
- Add comprehensive error classification (timeout, transient, permanent)
- Implement retry logic for transient failures
- Create summary reporting with success/failure breakdown
- Handle graceful degradation when models fail

### 7. Testing Infrastructure
- Replace existing tests with comprehensive test suite
- Add unit tests for config resolution, command construction, timeout/retry logic
- Create integration tests with mock `llm` subprocess
- Add golden file tests for output formats

### 8. Documentation Updates
- Update README with new functionality and usage examples
- Update CLI help text and command descriptions
- Add example configuration files

## File Structure Changes

```
prompter/
├── __init__.py (version only)
├── cli.py (main CLI interface)
├── core.py (execution engine)
├── config.py (configuration management)
├── models.py (data models for results/manifest)
├── utils.py (helpers, error handling)
└── constants.py (defaults, error messages)
```

## Detailed Implementation Steps

### Phase 1: Foundation
1. **Update Dependencies**
   - Add `PyYAML>=6.0.0` to pyproject.toml
   - Update project description and remove placeholder content

2. **Create Core Data Models** (`models.py`)
   ```python
   @dataclass
   class ModelResult:
       model: str
       status: Literal["ok", "error", "timeout"]
       duration_ms: int
       exit_code: int
       text: str
       meta: Dict[str, Any]
       command: List[str]
       stderr_tail: str

   @dataclass
   class RunManifest:
       cli_args: List[str]
       resolved_models: List[str]
       timestamp: str
       hostname: str
       git_sha: Optional[str]
       config_paths_used: List[str]
       llm_version: Optional[str]
       os_info: str
   ```

3. **Create Constants** (`constants.py`)
   - Default values for timeout, retries, parallel execution
   - Error message templates
   - Output directory patterns

### Phase 2: Configuration System
4. **Configuration Management** (`config.py`)
   - YAML config loading with precedence rules
   - Schema validation
   - Default value merging
   - Model list resolution logic

### Phase 3: Core Engine
5. **Utility Functions** (`utils.py`)
   - Error classification (transient vs permanent)
   - Retry logic with exponential backoff
   - Output directory creation
   - Command line argument forwarding

6. **Execution Engine** (`core.py`)
   - Async subprocess management
   - Concurrency control with semaphores
   - Real-time output streaming with model prefixes
   - Result collection and artifact generation

### Phase 4: CLI Interface
7. **CLI Overhaul** (`cli.py`)
   - Replace typer commands with single main command
   - Argument parsing with passthrough support
   - Dry-run mode implementation
   - Integration with core execution engine

8. **App Integration** (`app.py`)
   - Remove old greeting functions
   - Add orchestration logic
   - Integrate all components

### Phase 5: Testing & Documentation
9. **Test Suite Replacement**
   - Unit tests for each module
   - Integration tests with mock subprocess
   - Golden file tests for output formats
   - Error handling edge cases

10. **Documentation Updates**
    - Comprehensive README with examples
    - CLI help text
    - Configuration file examples

## Key Technical Decisions

### Architecture Patterns
- **Async/await**: Use asyncio for concurrent subprocess execution
- **Data Classes**: Use dataclasses for structured data (results, manifest)
- **Type Hints**: Comprehensive type annotation throughout
- **Error Handling**: Structured exception hierarchy with retry logic

### Dependencies Strategy
- **Minimal External Dependencies**: Only add PyYAML
- **Standard Library First**: Leverage asyncio, subprocess, pathlib
- **Compatibility**: Maintain Python 3.12+ requirement

### CLI Design Philosophy
- **Transparency**: Pass through nearly all `llm` flags unchanged
- **Flexibility**: Support both CLI args and config files
- **Usability**: Clear error messages and helpful defaults
- **Scriptability**: Support quiet mode and structured output

### Output Strategy
- **Streaming by Default**: Real-time feedback with model prefixes
- **Structured Artifacts**: JSON/JSONL for programmatic consumption
- **Raw Preservation**: Keep original stdout/stderr for debugging
- **Timestamped Runs**: Immutable output directories

## Testing Strategy

### Unit Tests
- Configuration precedence and merging
- Model list resolution
- Command construction with passthrough args
- Error classification and retry logic
- Output directory structure

### Integration Tests
- Full workflow with mock `llm` subprocess
- Streaming output verification
- Artifact generation validation
- Error handling scenarios

### Golden Tests
- Fixed input → expected manifest.json
- Fixed input → expected results.jsonl
- CLI help output verification

## Risk Mitigation

### Subprocess Management
- Proper cleanup of child processes
- Signal handling for graceful shutdown
- Resource limits and timeouts

### Error Recovery
- Graceful degradation when models fail
- Clear error reporting without stack traces
- Retry logic for transient failures

### User Experience
- Comprehensive help text and examples
- Validation of `llm` availability
- Clear progress indicators

## Success Criteria

### Functional Requirements
- ✅ Accept model list via CLI or config
- ✅ Execute `llm` concurrently across models
- ✅ Stream tagged output to console
- ✅ Generate structured artifacts
- ✅ Handle failures gracefully

### Quality Requirements
- ✅ Comprehensive test coverage (>90%)
- ✅ Type checking passes (pyright)
- ✅ Linting passes (ruff)
- ✅ Performance: handle 10+ models efficiently

### Usability Requirements
- ✅ Clear CLI interface matching design spec
- ✅ Helpful error messages
- ✅ Comprehensive documentation
- ✅ Easy installation and setup