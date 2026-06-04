# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Pydantic models for API responses."""


from typing import Any

from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    run_id: str
    status: str
    message: str
    session_count: int = 0


class StageInfo(BaseModel):
    status: str
    items: int | None = None


class RunSummary(BaseModel):
    run_id: str
    status: str
    stages: dict[str, StageInfo | dict[str, Any]]
