# Blackbox

Analysis engine for AI coding session traces. Ingests JSONL logs from Claude Code, Codex CLI, or pi.dev, runs a 9-stage LLM pipeline, and surfaces root causes, recurring failures, and anti-patterns.

## Demo

<p align="center">
  <b>Session browser</b><br/>
  <img src="docs/demo-browser.png" alt="Session browser" width="80%" />
</p>

<p align="center">
  <b>Splash screen</b><br/>
  <img src="docs/demo-splash.png" alt="Splash screen" width="80%" />
</p>

<p align="center">
  <b>Live progress</b><br/>
  <img src="docs/demo-progress.png" alt="Live progress" width="80%" />
</p>

## What it does

- **Multi-source ingestion** — accepts traces from Claude Code, Codex CLI, pi.dev, and more
- **9-stage LLM pipeline** — classifies, analyzes root causes, clusters patterns, scores severity
- **Disk persistence + resume** — stage outputs saved to disk; server restart picks up where it left off
- **DeepSeek V4 Pro support** — json_object response format, retry logic, structured logging

## How it works

```mermaid
flowchart TD
    subgraph Upload
        A["POST /analyze<br/>upload JSONL files"] --> B["Detect source<br/>_detect_source()"]
        B --> C["Normalize<br/>_normalize_file()"]
    end

    C --> D["Return 202 Accepted<br/>run_id → background task"]

    subgraph Pipeline
        P0["P0 Normalize<br/>count + index messages"]
        P1["P1 Classify<br/>LLM label each user turn<br/>batches run concurrently"]
        P2["P2 Context<br/>build windows around triggers"]
        P3["P3 Root-Cause<br/>LLM per trigger window"]
        P4a["P4a Behavior<br/>rule type + confidence"]
        P4b["P4b Cluster<br/>group recurring patterns"]
        P4c["P4c Convention<br/>dont_do / do_instead"]
        P5["P5 Aggregate<br/>deduplicate + score severity"]
        P6["P6 Scope<br/>map to repos + devs"]
    end

    subgraph Client
        POLL["GET /runs/:id<br/>poll status"]
        OUT["GET /runs/:id/findings<br/>recurring findings JSON"]
    end

    P0 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4a
    P3 --> P4b
    P3 --> P4c
    P4a --> P5
    P4b --> P5
    P4c --> P5
    P5 --> P6
    P6 --> POLL
    POLL --> OUT
```

## Quick Start

```bash
cp .env.example .env
# edit .env and add your OPENAI_API_KEY

uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
uv run quickcall  # Launch TUI (connects to http://localhost:8000)
```

The API binds to `0.0.0.0` (all interfaces). The CLI defaults to `localhost:8000`. If the API is running on a different host or port, set `BLACKBOX_API_URL` before launching the TUI:

```bash
export BLACKBOX_API_URL=http://192.168.1.42:8000
uv run quickcall
```

## Features

- Multi-source session analysis (Claude, Codex, pi, Gemini, Cursor)
- 9-stage LLM pipeline with live progress
- Disk persistence + resume
- DeepSeek V4 Pro support
- 80 tests

## Docs

- [API Reference](docs/api.md)
- [CLI Guide](docs/cli.md)
- [Pipeline](docs/pipeline.md)
- [Configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Agent Guide](AGENTS.md)

## License

Apache 2.0 — see [LICENSE](LICENSE).
