# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for RunStore."""

import tempfile

from src.storage.disk_store import DiskStore
from src.storage.run_store import RunStore


def test_runstore_creates_run_with_all_stages():
    store = RunStore()
    run = store.create_run("test-1")
    assert run.run_id == "test-1"
    assert run.status == "pending"
    assert "p1_classify" in run.stages
    assert run.stages["p1_classify"].status == "pending"
    assert "p3_rca" in run.stages
    assert "p5_aggregate" in run.stages


def test_runstore_updates_stage():
    store = RunStore()
    store.create_run("test-1")
    store.update_stage("test-1", "p1_classify", status="running")
    run = store.get_run("test-1")
    assert run.stages["p1_classify"].status == "running"
    assert run.stages["p1_classify"].started_at is not None


def test_runstore_updates_stage_with_data():
    store = RunStore()
    store.create_run("test-1")
    store.update_stage("test-1", "p1_classify", status="done", data={"items": 10})
    run = store.get_run("test-1")
    assert run.stages["p1_classify"].status == "done"
    assert run.stages["p1_classify"].data == {"items": 10}
    assert run.stages["p1_classify"].completed_at is not None


def test_runstore_get_stage_output():
    store = RunStore()
    store.create_run("test-1")
    store.update_stage("test-1", "p1_classify", status="done", data={"items": 10})
    assert store.get_stage_output("test-1", "p1_classify") == {"items": 10}


def test_runstore_get_stage_output_not_found():
    store = RunStore()
    store.create_run("test-1")
    assert store.get_stage_output("test-1", "p1_classify") is None


def test_disk_store_save_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DiskStore(tmpdir)
        store.save_stage("run_123", "p1_classify", {"trigger_count": 5})

        data = store.load_stage("run_123", "p1_classify")
        assert data["trigger_count"] == 5
        assert store.run_exists("run_123")
        assert "p1_classify" in store.list_stages("run_123")


def test_disk_store_list_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DiskStore(tmpdir)
        store.save_stage("run_a", "p1_classify", {"x": 1})
        store.save_stage("run_b", "p3_rca", {"y": 2})
        runs = store.list_runs()
        assert set(runs) == {"run_a", "run_b"}


def test_disk_store_load_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DiskStore(tmpdir)
        assert store.load_stage("missing", "p1_classify") is None
        assert store.list_stages("missing") == []


def test_runstore_with_disk_persists_on_done():
    with tempfile.TemporaryDirectory() as tmpdir:
        disk = DiskStore(tmpdir)
        store = RunStore(disk_store=disk)
        store.create_run("test-1")
        store.update_stage("test-1", "p1_classify", status="done", data={"items": 10})

        loaded = disk.load_stage("test-1", "p1_classify")
        assert loaded is not None
        assert loaded["status"] == "done"
        assert loaded["data"] == {"items": 10}


def test_runstore_updates_run_status():
    store = RunStore()
    store.create_run("test-1")
    store.update_run_status("test-1", "running")
    assert store.get_run("test-1").status == "running"


def test_runstore_list_runs():
    store = RunStore()
    store.create_run("test-1")
    store.create_run("test-2")
    runs = store.list_runs()
    assert len(runs) == 2
    assert {r.run_id for r in runs} == {"test-1", "test-2"}


def test_runstore_run_summary():
    store = RunStore()
    store.create_run("test-1")
    store.update_stage("test-1", "p1_classify", status="done", data={"items": 10, "triggers": 3})
    store.update_stage("test-1", "p3_rca", status="done", data={"findings": 5})
    summary = store.get_run_summary("test-1")
    assert summary["run_id"] == "test-1"
    assert summary["stages"]["p1_classify"]["status"] == "done"
    assert summary["stages"]["p1_classify"]["items"] == 10
    assert summary["stages"]["p3_rca"]["findings"] == 5
