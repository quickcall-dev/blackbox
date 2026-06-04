# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""FastAPI application for the Blackbox."""


import json
import logging
import re
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from src.config import settings
from src.llm.client import AsyncLLMClient
from src.models import AnalyzeResponse
from src.normalizer.claude_code_transform import normalize_claude_code
from src.normalizer.codex_cli_transform import normalize_codex_cli
from src.normalizer.pi_transform import normalize_pi
from src.pipeline.orchestrator import Pipeline
from src.storage.disk_store import DiskStore
from src.storage.run_store import RunStore


def create_app(
    *,
    run_store: RunStore | None = None,
    pipeline: Pipeline | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        disk = DiskStore(settings.temp_dir)
        if run_store is not None:
            app.state.run_store = run_store
            if getattr(app.state.run_store, "_disk", None) is None:
                app.state.run_store._disk = disk
        else:
            app.state.run_store = RunStore(disk_store=disk)
        app.state.pipeline = pipeline
        if app.state.pipeline is None:
            app.state.pipeline = _build_default_pipeline(app.state.run_store)
        yield

    app = FastAPI(title="Standalone Trace Analyzer", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": settings.model}

    @app.post("/analyze", status_code=202, response_model=AnalyzeResponse)
    async def analyze(
        request: Request,
        background_tasks: BackgroundTasks,
        source: str | None = None,
    ) -> AnalyzeResponse:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        files = await _extract_uploaded_files(request)

        if not files:
            raise HTTPException(status_code=400, detail="At least one file upload is required")

        sessions: dict[str, dict[str, Any]] = {}
        for filename, content in files:
            detected_source = source or _detect_source(filename, content)
            file_sessions = _normalize_file(filename, content, detected_source)
            sessions.update(file_sessions)

        app.state.run_store.create_run(run_id)
        background_tasks.add_task(_run_pipeline, app.state.pipeline, run_id, sessions)

        return AnalyzeResponse(
            run_id=run_id,
            status="pending",
            message=f"Analysis started for {len(sessions)} session(s)",
            session_count=len(sessions),
        )

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        run = app.state.run_store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return app.state.run_store.get_run_summary(run_id)

    @app.get("/runs/{run_id}/stages/{stage_name}")
    async def get_stage(run_id: str, stage_name: str) -> Any:
        run = app.state.run_store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if stage_name not in run.stages:
            raise HTTPException(status_code=404, detail="Stage not found")

        stage = run.stages[stage_name]
        if stage.status == "error":
            return {"status": "error", "error": stage.error}
        if stage.status in ("pending", "running"):
            raise HTTPException(status_code=404, detail="Stage output not available yet")

        data = app.state.run_store.get_stage_output(run_id, stage_name)
        if data is None:
            return {}
        return data

    @app.get("/runs/{run_id}/findings")
    async def get_findings(run_id: str) -> Any:
        findings = await get_stage(run_id, "p5_aggregate")
        return findings.get("filtered_findings", findings)

    @app.get("/runs/{run_id}/findings/all")
    async def get_all_findings(run_id: str) -> Any:
        return await get_stage(run_id, "p5_aggregate")

    return app


app = create_app()


def _build_default_pipeline(store: RunStore) -> Pipeline:
    llm_client = AsyncLLMClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        concurrency=settings.concurrency,
        model=settings.model,
    )
    return Pipeline(llm_client=llm_client, store=store)


def _detect_source(filename: str, content: bytes) -> str:
    lowered_name = filename.lower()
    if "claude" in lowered_name:
        return "claude_code"
    if "codex" in lowered_name:
        return "codex_cli"
    if ".pi" in lowered_name or "pi-" in lowered_name:
        return "pi"

    preview = content[:1024].decode("utf-8", errors="ignore")
    compact = preview.replace(" ", "")

    # Pi markers
    pi_markers = ('"type":"session"' in compact or '"type":"message"' in compact or '"type":"model_change"' in compact)
    # Claude markers
    claude_markers = ('"sessionId"' in preview) and ('"version"' in preview or '"gitBranch"' in preview or '"parentUuid"' in preview or '"uuid"' in preview)

    if pi_markers and not claude_markers:
        return "pi"
    if claude_markers:
        return "claude_code"
    # Any file with sessionId is likely claude
    if '"sessionId"' in preview:
        return "claude_code"
    # Any file with type:user and no pi markers is claude
    if '"type":"user"' in compact:
        return "claude_code"
    # Any file that looks like JSONL with a type field
    if '"type":"' in compact:
        try:
            first_line = preview.split('\n')[0].strip()
            if first_line:
                obj = json.loads(first_line)
                if isinstance(obj, dict) and "type" in obj:
                    return "pi"
        except Exception:
            pass
    return "unknown"


def _safe_parse_jsonl(content: bytes) -> list[dict[str, Any]]:
    """Parse JSONL lines, skipping malformed ones."""
    result = []
    for line in content.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def _normalize_file(filename: str, content: bytes, source: str) -> dict[str, dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    if source == "claude_code":
        lines = _safe_parse_jsonl(content)
        messages = normalize_claude_code(lines, filename)
    elif source == "pi":
        lines = _safe_parse_jsonl(content)
        messages = normalize_pi(lines, filename)
    elif source == "codex_cli":
        lines = _safe_parse_jsonl(content)
        messages = normalize_codex_cli(lines, filename)
    else:
        # Try pi as fallback for unknown sources
        try:
            lines = _safe_parse_jsonl(content)
            messages = normalize_pi(lines, filename)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    session_id = messages[0].session_id if messages else "unknown"
    if session_id == "unknown" and lines:
        for line in lines:
            if isinstance(line, dict):
                sid = line.get("sessionId") or line.get("session_id")
                if sid:
                    session_id = sid
                    break
    result: dict[str, Any] = {
        "session_id": session_id,
        "source": source,
        "messages": {},
        "tool_calls": {},
        "tool_results": {},
    }
    for i, msg in enumerate(messages):
        result["messages"][f"m{i}"] = {
            "content": msg.content or "",
            "msg_type": msg.msg_type,
            "timestamp": msg.timestamp,
        }
    return {session_id: result}


async def _extract_uploaded_files(request: Request) -> list[tuple[str, bytes]]:
    content_type = request.headers.get("content-type", "")
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if match is None:
        raise HTTPException(status_code=400, detail="Missing multipart boundary")

    boundary = f"--{match.group(1)}".encode()
    body = await request.body()

    files: list[tuple[str, bytes]] = []
    for part in body.split(boundary):
        if b'name="file"' not in part:
            continue
        header_block, separator, payload = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        filename_match = re.search(
            rb'filename="([^"]*)"',
            header_block,
        )
        filename = (
            filename_match.group(1).decode("utf-8", errors="ignore")
            if filename_match is not None
            else ""
        )
        files.append((filename, payload.rstrip(b"\r\n-")))

    if not files:
        raise HTTPException(status_code=400, detail="File upload is required")
    return files


async def _run_pipeline(
    pipeline: Pipeline,
    run_id: str,
    sessions: dict[str, dict[str, Any]],
) -> None:
    try:
        await pipeline.run(run_id, sessions)
    except Exception:  # pragma: no cover - defensive error path
        logging.exception("Pipeline background task failed for run %s", run_id)
        store: RunStore = pipeline.store
        store.update_run_status(run_id, "error")
        run = store.get_run(run_id)
        if run is not None:
            run.error = traceback.format_exc()
