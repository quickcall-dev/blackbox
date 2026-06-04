# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for pipeline orchestrator."""

import asyncio
import logging

import pytest

from src.pipeline.enrichment import phase4a_behavior_classify
from src.pipeline.orchestrator import MockLLMClient, Pipeline
from src.rca.prompts import (
    BEHAVIOR_SCHEMA,
    CLUSTER_SCHEMA,
    CONVENTION_SCHEMA,
)
from src.storage.run_store import RunStore


def build_minimal_session():
    """Return a minimal raw session dict."""
    return {
        "session_id": "s1",
        "source": "claude_code",
        "messages": {
            "m1": {
                "content": "implement feature",
                "msg_type": "user",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            "m2": {
                "content": "ok done",
                "msg_type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
            },
            "m3": {
                "content": "wrong approach",
                "msg_type": "user",
                "timestamp": "2026-01-01T00:00:02Z",
            },
            "m4": {
                "content": "fixed",
                "msg_type": "assistant",
                "timestamp": "2026-01-01T00:00:03Z",
            },
        },
        "tool_calls": {},
        "tool_results": {},
    }


@pytest.mark.anyio
async def test_pipeline_full_run_with_mock():
    mock = MockLLMClient()
    mock.set_response(
        "classify",
        {
            "classifications": [
                {"turn": 0, "label": "new_task"},
                {"turn": 2, "label": "correction"},
            ]
        },
    )
    mock.set_response(
        "rca",
        {
            "is_correction": True,
            "correction_turn": 2,
            "what_ai_did": "wrong approach",
            "root_cause": "didn't ask",
            "what_ai_should_have_done": "ask first",
            "category": "wrong_approach",
            "severity": 3,
            "files_involved": ["a.py"],
            "specificity": 7,
            "agents_md_rule": "always ask before changing approach",
        },
    )
    mock.set_response(
        "behavior",
        {
            "classifications": [
                {
                    "index": 0,
                    "rule_type": "agent_behavior",
                    "confidence": "high",
                    "requires_code_change": False,
                    "reason": "process issue",
                }
            ]
        },
    )
    mock.set_response(
        "cluster",
        {
            "patterns": [
                {
                    "label": "ask first",
                    "description": "ask before changing",
                    "finding_indices": [0],
                }
            ],
            "one_off_indices": [],
        },
    )
    mock.set_response(
        "convention",
        {
            "results": [
                {
                    "index": 0,
                    "is_convention": False,
                    "convention_type": "none",
                    "dont_do": "",
                    "do_instead": "",
                    "confidence": "low",
                }
            ]
        },
    )

    store = RunStore()
    pipeline = Pipeline(mock, store)
    sessions = {"s1": build_minimal_session()}

    await pipeline.run("test-run", sessions)

    run = store.get_run("test-run")
    assert run.status == "done"
    assert store.get_stage_output("test-run", "p1_classify") is not None
    assert store.get_stage_output("test-run", "p3_rca") is not None
    assert store.get_stage_output("test-run", "p5_aggregate") is not None
    summary = store.get_run_summary("test-run")
    assert summary["stages"]["p5_aggregate"]["status"] == "done"


@pytest.mark.anyio
async def test_pipeline_empty_session_completes():
    mock = MockLLMClient()

    store = RunStore()
    pipeline = Pipeline(mock, store)
    sessions = {}
    await pipeline.run("empty-run", sessions)

    run = store.get_run("empty-run")
    assert run.status == "done"
    assert store.get_stage_output("empty-run", "p3_rca") == {"findings": []}


@pytest.mark.anyio
async def test_pipeline_handles_llm_failure_gracefully():
    mock = MockLLMClient()
    mock.set_response("classify", Exception("timeout"))

    store = RunStore()
    pipeline = Pipeline(mock, store)
    sessions = {"s1": build_minimal_session()}
    await pipeline.run("fail-run", sessions)

    run = store.get_run("fail-run")
    assert run.status == "error"
    assert "timeout" in str(run.error).lower()


@pytest.mark.anyio
async def test_pipeline_no_triggers_skips_rca():
    mock = MockLLMClient()
    mock.set_response(
        "classify",
        {
            "classifications": [
                {"turn": 0, "label": "new_task"},
                {"turn": 1, "label": "acceptance"},
            ]
        },
    )

    store = RunStore()
    pipeline = Pipeline(mock, store)
    sessions = {"s1": build_minimal_session()}
    await pipeline.run("no-triggers", sessions)

    run = store.get_run("no-triggers")
    assert run.status == "done"
    rca_data = store.get_stage_output("no-triggers", "p3_rca")
    assert rca_data == {"findings": []}
    aggregate = store.get_stage_output("no-triggers", "p5_aggregate")
    assert aggregate["total_findings"] == 0


@pytest.mark.anyio
async def test_pipeline_no_triggers_avoids_downstream_llm_calls():
    class StrictMockLLMClient(MockLLMClient):
        def _detect_phase(self, system: str) -> str:
            phase = super()._detect_phase(system)
            if phase in {"rca", "behavior", "cluster", "convention"}:
                raise AssertionError(f"unexpected downstream LLM call for {phase}")
            return phase

    mock = StrictMockLLMClient()
    mock.set_response(
        "classify",
        {
            "classifications": [
                {"turn": 0, "label": "new_task"},
                {"turn": 1, "label": "acceptance"},
            ]
        },
    )

    store = RunStore()
    pipeline = Pipeline(mock, store)

    await pipeline.run("strict-no-triggers", {"s1": build_minimal_session()})

    assert store.get_run("strict-no-triggers").status == "done"
    assert store.get_stage_output("strict-no-triggers", "p3_rca") == {"findings": []}


def test_pipeline_uses_shared_enrichment_schemas():
    from src import pipeline as pipeline_module

    assert pipeline_module.BEHAVIOR_SCHEMA == BEHAVIOR_SCHEMA
    assert pipeline_module.CLUSTER_SCHEMA == CLUSTER_SCHEMA
    assert pipeline_module.CONVENTION_SCHEMA == CONVENTION_SCHEMA


@pytest.mark.anyio
async def test_enrichment_batches_findings():
    mock = MockLLMClient()
    mock.set_response(
        "behavior",
        {
            "classifications": [
                {
                    "index": 0,
                    "rule_type": "agent_behavior",
                    "confidence": "high",
                    "requires_code_change": False,
                    "reason": "process",
                },
                {
                    "index": 1,
                    "rule_type": "code_correctness",
                    "confidence": "high",
                    "requires_code_change": True,
                    "reason": "code",
                },
            ]
        },
    )

    findings = [
        {"agents_md_rule": "rule 1"},
        {"agents_md_rule": "rule 2"},
    ]

    result = await phase4a_behavior_classify(
        findings, mock, asyncio.Semaphore(10), logging.getLogger("test"),
    )

    assert result[0]["rule_type"] == "agent_behavior"
    assert result[1]["rule_type"] == "code_correctness"
