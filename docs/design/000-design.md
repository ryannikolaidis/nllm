# Multi-Model Fan-Out Wrapper for `llm` — Design

## Goals & Non-Goals

**Goals**
- Accept a set of model IDs via CLI flags or, if omitted, fall back to a config file.
- Execute the same `llm` prompt concurrently across models.
- Be transparent: pass through nearly all `llm` flags (temperature, system, files, etc.).
- Provide structured outputs (on disk) and readable console output (streamed or buffered).
- Robust failure handling: per-model timeouts, retries, and clear error summaries.

**Non-Goals**
- Reimplement `llm`’s providers, auth flows, or caching.
- Build a UI; this is a CLI utility first.
- Long-running orchestration or eval frameworks (can be added later).

---

## High-Level Concept

A tiny CLI (working name: `prompter`) that:
1. Resolves a **models list** from either CLI (`-m/--model`) or config files (precedence: `./.prompter-config.yaml` → `~/.prompter/config.yaml`).
2. Constructs **per-model `llm` invocations** for the same prompt and options.
3. Runs them **in parallel** (Python `asyncio` + subprocesses, or shell `xargs -P` if using bash mode).
4. **Collects outputs**: streams to console (tagged by model) and writes artifacts (one JSONL row per model, plus a merged manifest).
5. Reports a **summary** (latency, token/cost if available, successes/failures).

---

## CLI Surface

```
prompter [OPTIONS] -- [PROMPT and/or llm passthrough args]

Options:
  -m, --model TEXT           Repeatable. E.g. -m gpt-4 -m claude-3-sonnet
  -c, --config PATH          Optional override config path
  -o, --outdir PATH          Output directory (default: ./prompter-runs/<timestamp>)
  --parallel N               Concurrency (default: number of models or CPU count)
  --timeout SECONDS          Per-model timeout
  --retries N                Per-model retries on transient errors (default: 0 or 1)
  --stream/--no-stream       Stream model outputs to console as they arrive (default: --stream)
  --raw                      Write raw stdout/stderr per model to files (in addition to parsed content)
  --dry-run                  Show the resolved commands without executing
  -q, --quiet                Reduce console noise (errors still shown)
  --version
  --help

Passthrough:
  Anything after `--` is forwarded to `llm`.
  Examples:
    prompter -m gpt-4 -m claude-3-sonnet -- "Explain CRDTs in 2 paragraphs"
    prompter -- -m gpt-4 -t 0.2 "Explain CRDTs"
```

**Note on prompt source**: Like `llm`, support:
- Positional prompt string after `--`
- Or `--prompt-file`, `--system`, input from STDIN, etc. The wrapper just forwards.

---

## Config Resolution

**Precedence**
1. `--config <path>` if provided
2. `./.prompter-config.yaml` (current directory)
3. `~/.prompter/config.yaml` (home directory)

**Schema**
```yaml
models:
  - "gpt-4"
  - "claude-3-sonnet"
  - "gemini-pro"

defaults:
  retries: 0
  stream: true
  outdir: "./prompter-runs"
```

- If `-m/--model` flags are provided, they **override** `models` from config.
- Missing fields fall back to app defaults.

**Validation**
- Ensure at least one model is available after resolution.
- Validate that `llm` is installed and models appear in `llm models` list (optional fast-fail).

---

## Execution Model

**Python approach (recommended)**
- Use `asyncio.create_subprocess_exec` to launch `llm` per model.
- Concurrency control via an `asyncio.Semaphore` sized to `--parallel`.
- Implement per-task timeout and retry policy.
- Streaming: read child stdout line-by-line; prefix with `[model]` for console.
- On completion, capture:
  - Exit code
  - Stdout/stderr (raw)
  - Parsed content (best effort; see Output Format)

**Bash alternative (minimal mode)**
- Compute the list of `llm` commands and feed into `xargs -P <N> -I{} sh -c "{}"`.
- Less control over streaming, retries, and parsing; keep as a fallback.

---

## Output & Artifacts

**Directory layout (per run):**
```
<outdir>/<timestamp>/
  manifest.json
  raw/
    <model>.stdout.txt
    <model>.stderr.txt
  results.jsonl
  results/
    <model>.json            # parsed single-model result
```

**`manifest.json`**
- CLI args, resolved models
- Timestamp, hostname, git SHA (if inside a repo)
- Config paths used
- `llm` version, OS info

**`results.jsonl` (one line per model)**
```json
{
  "model": "gpt-4",
  "status": "ok" | "error" | "timeout",
  "duration_ms": 1234,
  "exit_code": 0,
  "text": "<final text content>",
  "meta": {
    "tokens_input": 123,
    "tokens_output": 456,
    "cost_estimated": 0.0123
  },
  "command": ["llm", "-m", "gpt-4", "..."],
  "stderr_tail": "..."
}
```

**Parsing strategy**
- By default, capture `stdout` as text.
- If the user passes `llm` options that enforce JSON output (e.g., a hypothetical `--json` or a template), store raw + parsed.
- If not JSON, store `text` verbatim and keep raw files for fidelity.

---

## Error Handling & Retries

- **Timeouts**: kill the subprocess and record `"status": "timeout"`.
- **Transient errors** (network, 5xx, provider backoffs): classify by regex on stderr; apply `--retries` with exponential backoff.
- **Permanent errors** (invalid model, auth): fail fast for that model and continue the batch.

**Exit code**
- `0` if all models succeeded
- `1` if any model failed/timeout

**Console summary example**
```
Summary (3 models):
  ✓ gpt-4            2.4s
  ✓ claude-3-sonnet  2.1s
  ✗ gemini-pro       timeout (60s)
Artifacts: ./prompter-runs/2025-09-28_12-30-05
```

---

## Streaming vs Buffered

- **Streaming mode (default)**: show lines as they arrive with `[model]` prefix. Good for interactive usage.
- **Buffered mode**: suppress live output, only show final summary; useful for scripting.

---

## Pass-Through of `llm` Features

Allow arbitrary `llm` flags to flow through:
- Temperature, system prompts, prompt files, images, attachments
- Provider-specific flags (the wrapper should not validate them)
- `llm` plugins (embeddings, tools) pass unchanged

**Caveat**: If a provider flag conflicts across models (e.g., specific to OpenAI only), it’s the user’s responsibility; wrapper should surface each model’s error clearly.

---

## Security & Credentials

- Do not read or write secrets.
- Assume `llm` is already configured with provider keys (`llm keys set ...`).
- Redact env vars and arguments in logs that look like secrets (simple regex).

---

## Extensibility Hooks (Optional, phased)

1. **Cost & token accounting**  
   If `llm` returns usage in stderr or structured output, parse and include in `meta`. Else allow user to provide a simple cost map per model in config:
   ```yaml
   costs:
     gpt-4:
       input_per_1k: 0.005
       output_per_1k: 0.015
   ```

2. **Prompt templating**  
   Allow `--vars file.yaml` to substitute variables in the prompt before invoking `llm` (preprocessing step), but keep it optional to avoid scope creep.

3. **Result diffing**  
   With `--compare`, generate a side-by-side diff or a short rubric score (e.g., length, presence of key terms).

4. **Eval mode**  
   Accept a YAML of prompts and run a matrix over models × prompts, writing a wide `jsonl` and a CSV summary.

---

## Testing Strategy

- **Unit tests**:  
  - Config precedence resolution (cwd vs home vs `--config`)  
  - Model list merging and overrides  
  - Command construction with passthrough args  
  - Timeout and retry logic (use a fake `llm` script)
- **Integration tests**:  
  - Run against a local fake `llm` that echoes inputs and delays output  
  - Verify streaming tagging, artifacts, exit codes
- **Golden tests**:  
  - Given fixed inputs, compare `manifest.json` and `results.jsonl` (ignoring volatile fields)

---

## Operational Notes

- **Dependencies**: Keep it light—Python standard library only (argparse/typer, asyncio, yaml via `PyYAML` as the only external dep). For bash mode, require `xargs`.
- **Performance**: Subprocess fan-out is typically I/O-bound; concurrency should be safe up to dozens of models.
- **Portability**: Works on macOS/Linux. Windows should be fine with Python subprocess; test CRLF and signaling.

---

## Example Flows (behavioral)

**1) Models via CLI**
```
prompter -m gpt-4 -m claude-3-sonnet -- "Summarize the paper in 5 bullets"
```
- Runs two `llm` calls in parallel.
- Streams `[gpt-4] ...` and `[claude-3-sonnet] ...`.
- Writes artifacts and prints a summary.

**2) Models from config**
```
# ./.prompter-config.yaml
models:
  - gpt-4
  - claude-3-sonnet
  - gemini-pro

prompter -- "What is vector quantization?"
```
- Uses the three configured models automatically.

**3) Dry run**
```
prompter -m gpt-4 --dry-run -- -t 0.3 "Plan a unit test strategy"
```
- Prints the exact `llm` command that would run, per model; doesn’t execute.

---

## Decision Points To Clarify

- Do you want **strict streaming** (interleaved lines) or **per-model blocks** in the console?
- How important is **structured usage/cost** capture at v1?
- Should the wrapper **validate models up front** by calling `llm models` (adds a small start-up cost) or fail lazily per model?
- Preferred **default concurrency**: match model count, or cap at CPU cores?
