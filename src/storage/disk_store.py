# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Disk-backed stage storage for pipeline resumeability."""

import json
from pathlib import Path
from typing import Any


class DiskStore:
    """Save/load stage outputs to disk as JSON."""

    def __init__(self, base_dir: str | Path = "/tmp/standalone-trace-analyzer/runs") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

    def _stage_path(self, run_id: str, stage_name: str) -> Path:
        return self._run_dir(run_id) / f"{stage_name}.json"

    def save_stage(self, run_id: str, stage_name: str, data: Any) -> None:
        """Write stage output to disk."""
        path = self._stage_path(run_id, stage_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    def load_stage(self, run_id: str, stage_name: str) -> Any:
        """Read stage output from disk. Returns None if not found."""
        path = self._stage_path(run_id, stage_name)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_runs(self) -> list[str]:
        """List all run IDs that have persisted data."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def run_exists(self, run_id: str) -> bool:
        return self._run_dir(run_id).exists()

    def list_stages(self, run_id: str) -> list[str]:
        """List all persisted stage names for a run."""
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return []
        return [p.stem for p in run_dir.glob("*.json")]
