# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Unified schema that all CLI formats transform into."""


from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TokenUsage:
    """Unified token usage metrics."""

    input: int = 0
    output: int = 0
    cached: int = 0
    thinking: int = 0


@dataclass
class ToolCall:
    """Normalized tool call information."""

    id: str
    name: str
    input: dict


@dataclass
class ToolResult:
    """Normalized tool result information."""

    call_id: str
    output: str
    status: Literal["success", "failure"]


@dataclass
class HookInfo:
    """Information about a hook execution."""

    event: str
    name: str
    command: str | None = None
    tool_use_id: str | None = None


@dataclass
class ProgressData:
    """Data for progress events."""

    progress_type: str
    hook_info: HookInfo | None = None
    stdout: str | None = None
    stderr: str | None = None


@dataclass
class SystemEventData:
    """Data for system events."""

    subtype: str
    duration_ms: int | None = None
    hook_count: int | None = None
    hook_infos: list[HookInfo] | None = None
    hook_errors: list[str] | None = None
    prevented_continuation: bool | None = None
    stop_reason: str | None = None


@dataclass
class QueueOperationData:
    """Data for queue/background task operations."""

    operation: str
    task_id: str | None = None
    status: str | None = None
    summary: str | None = None
    output_file: str | None = None


MessageType = Literal[
    "user",
    "assistant",
    "system",
    "tool_call",
    "tool_result",
    "info",
    "error",
    "progress",
    "system_event",
    "queue_operation",
    "file_snapshot",
    "summary",
    "compaction",
]

SourceType = Literal["claude_code", "codex_cli", "gemini_cli", "cursor", "cursor_vscdb", "pi"]


@dataclass
class SessionContext:
    """Per-session context: who is working and on what repo."""

    user_email: str | None = None
    user_name: str | None = None
    device_name: str | None = None
    device_id: str | None = None
    cwd: str | None = None
    repo_url: str | None = None
    repo_name: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    project_hash: str | None = None
    org: str | None = None


@dataclass
class NormalizedMessage:
    """Unified message format that all CLI sources transform into."""

    id: str
    session_id: str
    source: SourceType
    msg_type: MessageType
    timestamp: str
    source_schema_version: int = 1
    content: str | None = None
    tokens: TokenUsage = field(default_factory=TokenUsage)
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    thinking: str | None = None
    model: str | None = None
    progress_data: ProgressData | None = None
    system_event_data: SystemEventData | None = None
    queue_operation_data: QueueOperationData | None = None
    raw_data: dict[str, Any] | None = None
    session_context: SessionContext | None = None
    raw_file_path: str = ""
    raw_line_number: int | None = None
