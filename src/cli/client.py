# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""HTTP client for the Blackbox analysis API."""

import os
from pathlib import Path
import httpx

from src.cli.config import get_api_url


class BlackboxClient:
    """Async HTTP client wrapping Blackbox REST API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or get_api_url()).rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def health(self) -> bool:
        """Check if the API is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self._url("/health"), timeout=5)
                return resp.status_code == 200
        except Exception:
            return False

    async def analyze(self, files: list[Path], source: str | None = None) -> str:
        """Upload session files for analysis. Returns run_id."""
        params = {}
        if source:
            params["source"] = source

        async with httpx.AsyncClient(timeout=30) as client:
            form_files = []
            for file_path in files:
                form_files.append(
                    ("file", (file_path.name, file_path.read_bytes(), "application/octet-stream"))
                )
            resp = await client.post(self._url("/analyze"), files=form_files, params=params)
            resp.raise_for_status()
            return resp.json()["run_id"]

    async def get_run(self, run_id: str) -> dict:
        """Get run status and stage info."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._url(f"/runs/{run_id}"))
            resp.raise_for_status()
            return resp.json()

    async def get_findings(self, run_id: str) -> list[dict]:
        """Get filtered findings (recurring only)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._url(f"/runs/{run_id}/findings"))
            resp.raise_for_status()
            return resp.json()

    async def get_findings_all(self, run_id: str) -> dict:
        """Get all findings including metadata."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._url(f"/runs/{run_id}/findings/all"))
            resp.raise_for_status()
            return resp.json()
