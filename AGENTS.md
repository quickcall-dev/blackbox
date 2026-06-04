# Blackbox – Agent Guide

## What this repo is

Blackbox is the analysis engine inside QuickCall. It takes raw AI coding session traces (JSONL), runs a multi-stage LLM pipeline to find root causes, recurring failures, and anti-patterns, then feeds that back so future agent sessions improve.

## How to run

```bash
uv sync --extra dev
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## How to test

```bash
uv run pytest                  # all tests
uv run pytest tests/test_api.py -x  # just API tests, stop on first failure
```

## Key files to know

| File | What it does |
|------|-------------|
| `src/main.py` | FastAPI app, routes, file upload, source detection, normalization dispatch |
| `src/config.py` | Settings from env/.env |
| `src/models.py` | Pydantic response models |
| `src/pipeline/orchestrator.py` | Pipeline class — runs P0–P6 stages in order |
| `src/pipeline/annotator.py` | Annotates raw messages with tool calls, edits, thinking blocks |
| `src/pipeline/context_builder.py` | Builds context windows around trigger turns |
| `src/pipeline/dedup.py` | Deduplicates findings by similarity threshold |
| `src/classify/runner.py` | Classification runner — labels user messages via LLM |
| `src/classify/prompts.py` | Classification system prompt + JSON schema |
| `src/rca/prompts.py` | All analysis prompts and JSON schemas (RCA, behavior, cluster, convention) |
| `src/normalizer/unified.py` | NormalizedMessage — the universal format all sources map to |
| `src/llm/client.py` | Async LLM client (OpenAI-compatible API) |
| `src/storage/run_store.py` | In-memory store for run state and stage outputs |

## Architecture

See [docs/architecture.md](docs/architecture.md) for full Mermaid diagram, file structure, data flow, and pipeline stage details.

## How to add a new source format

1. Add transform in `src/normalizer/<source>_transform.py`
2. Add `normalize_<source>()` function returning `list[NormalizedMessage]`
3. Import and wire into `_normalize_file()` in `src/main.py`
4. Add detection heuristics in `_detect_source()` in `src/main.py`

## Conventions

- Python 3.14+, `uv` for package management
- All Python files start with: `# SPDX-License-Identifier: Apache-2.0` + `# Copyright 2025 QuickCall`
- `from __future__ import annotations` is banned — Python 3.14 doesn't need it
- Tests use `pytest` + `pytest-asyncio`, run from project root
- `.env`, `.venv`, `__pycache__`, `archive.tar.gz`, `*.log` are gitignored
