# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StageOutput:
    name: str
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    data: Any = None
    error: str | None = None


@dataclass
class Run:
    run_id: str
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error: str | None = None
    stages: dict[str, StageOutput] = field(default_factory=dict)


class RunStore:
    ALL_STAGES = [
        "p0_normalize",
        "p1_classify",
        "p2_context",
        "p3_rca",
        "p4a_behavior",
        "p4b_cluster",
        "p4c_convention",
        "p5_aggregate",
        "p6_scope",
    ]

    def __init__(self, disk_store: "DiskStore | None" = None) -> None:
        self._runs: dict[str, Run] = {}
        self._disk = disk_store

    def create_run(self, run_id: str) -> Run:
        run = Run(run_id=run_id)
        run.stages = {
            stage_name: StageOutput(name=stage_name) for stage_name in self.ALL_STAGES
        }
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def update_stage(
        self,
        run_id: str,
        stage_name: str,
        *,
        status: str | None = None,
        data: Any = None,
        error: str | None = None,
    ) -> None:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        stage = run.stages.get(stage_name)
        if stage is None:
            raise KeyError(f"Stage {stage_name} not found")

        if status is not None:
            stage.status = status
            if status == "running" and stage.started_at is None:
                stage.started_at = datetime.utcnow()
            if status in {"done", "error"}:
                if stage.started_at is None:
                    stage.started_at = datetime.utcnow()
                stage.completed_at = datetime.utcnow()

        if data is not None:
            stage.data = data

        if error is not None:
            stage.error = error

        if self._disk is not None and status in ("done", "error") and data is not None:
            self._disk.save_stage(run_id, stage_name, {"status": stage.status, "data": data, "error": error})

    def update_run_status(self, run_id: str, status: str) -> None:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        run.status = status
        if status in {"done", "error"}:
            run.completed_at = datetime.utcnow()

    def get_stage_output(self, run_id: str, stage_name: str) -> Any:
        run = self._runs.get(run_id)
        if run is None:
            return None

        stage = run.stages.get(stage_name)
        if stage is None:
            return None

        return stage.data

    def list_runs(self) -> list[Run]:
        return list(self._runs.values())

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            return {}

        result: dict[str, Any] = {
            "run_id": run.run_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error": run.error,
            "stages": {
                name: self._stage_summary(stage) for name, stage in run.stages.items()
            },
        }
        return result

    def _stage_summary(self, stage: StageOutput) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "status": stage.status,
            "started_at": stage.started_at.isoformat() if stage.started_at else None,
            "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
        }

        if isinstance(stage.data, dict):
            summary.update(stage.data)
        elif stage.data is not None:
            summary["data"] = stage.data

        if stage.error:
            summary["error"] = stage.error

        return summary
