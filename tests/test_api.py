# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for FastAPI routes."""

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.storage.run_store import RunStore

SAMPLE_JSONL = b'{"type":"user","uuid":"u1","sessionId":"s1","timestamp":"2026-01-01T00:00:00Z","message":{"content":"hello"}}\n'


@pytest.fixture
def client() -> TestClient:
    store = RunStore()

    class StubPipeline:
        def __init__(self, run_store: RunStore) -> None:
            self.store = run_store

        async def run(self, run_id: str, sessions: dict[str, dict]) -> None:
            self.store.update_run_status(run_id, "running")
            self.store.update_stage(
                run_id,
                "p0_normalize",
                status="done",
                data={"sessions": sessions, "count": len(sessions)},
            )
            self.store.update_stage(
                run_id,
                "p5_aggregate",
                status="done",
                data={
                    "findings": [],
                    "filtered_findings": [],
                    "total_findings": 0,
                    "total_sessions": len(sessions),
                },
            )
            self.store.update_run_status(run_id, "done")

    return TestClient(create_app(run_store=store, pipeline=StubPipeline(store)))


def test_health_check(client: TestClient):
    with client as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_post_analyze_returns_run_id(client: TestClient):
    with client as test_client:
        response = test_client.post("/analyze", files={"file": ("test.jsonl", SAMPLE_JSONL)})
    assert response.status_code == 202
    data = response.json()
    assert data["run_id"].startswith("run_")
    assert data["status"] == "pending"
    assert "1 session(s)" in data["message"]
    assert data["session_count"] == 1


def test_post_analyze_with_source_hint(client: TestClient):
    with client as test_client:
        response = test_client.post(
            "/analyze?source=claude_code",
            files={"file": ("test.jsonl", SAMPLE_JSONL)},
        )
    assert response.status_code == 202


def test_get_run_returns_status_and_stages(client: TestClient):
    with client as test_client:
        post = test_client.post("/analyze", files={"file": ("test.jsonl", SAMPLE_JSONL)})
        run_id = post.json()["run_id"]

        response = test_client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["status"] == "done"
    assert data["stages"]["p0_normalize"]["status"] == "done"
    assert data["stages"]["p5_aggregate"]["status"] == "done"


def test_get_stage_returns_output(client: TestClient):
    with client as test_client:
        post = test_client.post("/analyze", files={"file": ("test.jsonl", SAMPLE_JSONL)})
        run_id = post.json()["run_id"]
        response = test_client.get(f"/runs/{run_id}/stages/p0_normalize")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert "s1" in data["sessions"]


def test_get_findings_returns_filtered_findings(client: TestClient):
    with client as test_client:
        post = test_client.post("/analyze", files={"file": ("test.jsonl", SAMPLE_JSONL)})
        run_id = post.json()["run_id"]
        response = test_client.get(f"/runs/{run_id}/findings")

    assert response.status_code == 200
    assert response.json() == []


def test_get_findings_all_returns_all_findings(client: TestClient):
    with client as test_client:
        post = test_client.post("/analyze", files={"file": ("test.jsonl", SAMPLE_JSONL)})
        run_id = post.json()["run_id"]
        response = test_client.get(f"/runs/{run_id}/findings/all")

    assert response.status_code == 200
    data = response.json()
    assert data["findings"] == []
    assert data["filtered_findings"] == []
    assert data["total_findings"] == 0
    assert data["total_sessions"] == 1


def test_get_stage_without_output_returns_404():
    store = RunStore()
    run = store.create_run("run_pending")
    run.stages["p0_normalize"].status = "running"

    with TestClient(create_app(run_store=store, pipeline=None)) as client:
        response = client.get("/runs/run_pending/stages/p0_normalize")

    assert response.status_code == 404
    assert response.json() == {"detail": "Stage output not available yet"}


def test_post_analyze_multiple_sessions(client: TestClient):
    sample1 = b'{"type":"user","uuid":"u1","sessionId":"s1","timestamp":"2026-01-01T00:00:00Z","message":{"content":"hello"}}\n'
    sample2 = b'{"type":"user","uuid":"u2","sessionId":"s2","timestamp":"2026-01-01T00:00:00Z","message":{"content":"world"}}\n'

    with client as test_client:
        response = test_client.post(
            "/analyze",
            files=[
                ("file", ("s1.jsonl", sample1)),
                ("file", ("s2.jsonl", sample2)),
            ],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["session_count"] == 2
    assert "2 session(s)" in data["message"]


def test_get_nonexistent_run_returns_404(client: TestClient):
    with client as test_client:
        response = test_client.get("/runs/does-not-exist")
    assert response.status_code == 404
