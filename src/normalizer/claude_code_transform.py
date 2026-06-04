# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Transform Claude Code v1 session data to unified format."""


import re
from typing import Any

from .unified import (
    HookInfo,
    NormalizedMessage,
    ProgressData,
    QueueOperationData,
    SessionContext,
    SystemEventData,
    TokenUsage,
    ToolCall,
    ToolResult,
)


def extract_session_id(file_path: str) -> str:
    """Extract session ID from a Claude Code file path."""
    match = re.search(r"/([^/]+)\.jsonl$", file_path)
    if match:
        return match.group(1)
    return file_path


def extract_tokens(usage: dict[str, Any]) -> TokenUsage:
    """Extract token usage from Claude usage data."""
    return TokenUsage(
        input=usage.get("input_tokens", 0),
        output=usage.get("output_tokens", 0),
        cached=usage.get("cache_read_input_tokens", 0),
        thinking=0,
    )


def normalize_claude_code(lines: list[dict], file_path: str = "") -> list[NormalizedMessage]:
    """Normalize a Claude Code session."""
    messages: list[NormalizedMessage] = []
    for line_num, line in enumerate(lines, start=1):
        messages.extend(transform_claude_v1(line, file_path, line_num))
    return messages


def _extract_tool_results(
    blocks: list,
    line_uuid: str,
    session_id: str,
    file_path: str,
    line_num: int,
    timestamp: str,
    use_is_error: bool = False,
) -> list[NormalizedMessage]:
    messages = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        tool_output = block.get("content", "")
        if isinstance(tool_output, list):
            tool_output = "\n".join(
                part.get("text", str(part)) if isinstance(part, dict) else str(part)
                for part in tool_output
            )
        status = "failure" if use_is_error and block.get("is_error") else "success"
        messages.append(
            NormalizedMessage(
                id=f"{line_uuid}-{block.get('tool_use_id', '')}",
                session_id=session_id,
                source="claude_code",
                source_schema_version=1,
                msg_type="tool_result",
                timestamp=timestamp,
                tool_result=ToolResult(
                    call_id=block.get("tool_use_id", ""),
                    output=str(tool_output),
                    status=status,
                ),
                raw_file_path=file_path,
                raw_line_number=line_num,
            )
        )
    return messages


def transform_claude_v1(line: dict[str, Any], file_path: str, line_num: int) -> list[NormalizedMessage]:
    """Transform a single Claude Code JSONL line."""
    line_type = line.get("type")
    session_id = line.get("sessionId") or extract_session_id(file_path)

    if line_type == "user":
        return _transform_user_message(line, session_id, file_path, line_num)
    if line_type == "assistant":
        return _transform_assistant_message(line, session_id, file_path, line_num)
    if line_type == "result":
        return _transform_result_message(line, session_id, file_path, line_num)
    if line_type == "progress":
        return _transform_progress_message(line, session_id, file_path, line_num)
    if line_type == "system":
        return _transform_system_message(line, session_id, file_path, line_num)
    if line_type == "queue-operation":
        return _transform_queue_operation(line, session_id, file_path, line_num)
    if line_type == "file-history-snapshot":
        return _transform_file_snapshot(line, session_id, file_path, line_num)
    if line_type == "summary":
        return _transform_summary(line, session_id, file_path, line_num)

    return [
        NormalizedMessage(
            id=line.get("uuid", f"unknown-{line_num}"),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="info",
            timestamp=line.get("timestamp", ""),
            content=f"Unknown message type: {line_type}",
            raw_data=line,
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_user_message(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    message = line.get("message", {})
    content = message.get("content")
    if isinstance(content, list):
        return _extract_tool_results(
            content,
            line["uuid"],
            session_id,
            file_path,
            line_num,
            line.get("timestamp", ""),
            use_is_error=False,
        )

    return [
        NormalizedMessage(
            id=line.get("uuid", ""),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="user",
            timestamp=line.get("timestamp", ""),
            content=content if isinstance(content, str) else str(content),
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_assistant_message(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    message = line.get("message", {})
    content_blocks = message.get("content", [])
    usage = message.get("usage", {})
    tokens = extract_tokens(usage)
    model = message.get("model")

    messages: list[NormalizedMessage] = []
    text_parts: list[str] = []
    thinking_parts: list[str] = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "thinking":
            thinking_parts.append(block.get("thinking", ""))
        elif block_type == "tool_use":
            messages.append(
                NormalizedMessage(
                    id=block.get("id", f"{line.get('uuid', '')}-tool"),
                    session_id=session_id,
                    source="claude_code",
                    source_schema_version=1,
                    msg_type="tool_call",
                    timestamp=line.get("timestamp", ""),
                    tool_call=ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        input=block.get("input", {}),
                    ),
                    model=model,
                    raw_file_path=file_path,
                    raw_line_number=line_num,
                )
            )

    combined_text = "\n\n".join(text_parts) if text_parts else None
    combined_thinking = "\n\n".join(thinking_parts) if thinking_parts else None
    if combined_text or combined_thinking:
        messages.insert(
            0,
            NormalizedMessage(
                id=line.get("uuid", ""),
                session_id=session_id,
                source="claude_code",
                source_schema_version=1,
                msg_type="assistant",
                timestamp=line.get("timestamp", ""),
                content=combined_text,
                tokens=tokens,
                thinking=combined_thinking,
                model=model,
                session_context=_extract_session_context(line),
                raw_file_path=file_path,
                raw_line_number=line_num,
            ),
        )

    return messages


def _transform_result_message(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    message = line.get("message", {})
    content = message.get("content")
    if isinstance(content, list):
        return _extract_tool_results(
            content,
            line.get("uuid", ""),
            session_id,
            file_path,
            line_num,
            line.get("timestamp", ""),
            use_is_error=True,
        )
    return []


def _transform_progress_message(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    data = line.get("data", {})
    progress_type = data.get("type", "unknown")
    hook_info = None
    if progress_type == "hook_progress":
        hook_info = HookInfo(
            event=data.get("hookEvent", ""),
            name=data.get("hookName", ""),
            command=data.get("command"),
            tool_use_id=line.get("toolUseID"),
        )

    return [
        NormalizedMessage(
            id=line.get("uuid", f"progress-{line_num}"),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="progress",
            timestamp=line.get("timestamp", ""),
            progress_data=ProgressData(
                progress_type=progress_type,
                hook_info=hook_info,
                stdout=data.get("stdout"),
                stderr=data.get("stderr"),
            ),
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_system_message(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    raw_hook_infos = line.get("hookInfos", [])
    hook_infos = None
    if raw_hook_infos:
        hook_infos = [HookInfo(event="", name="", command=item.get("command")) for item in raw_hook_infos]

    return [
        NormalizedMessage(
            id=line.get("uuid", f"system-{line_num}"),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="system_event",
            timestamp=line.get("timestamp", ""),
            system_event_data=SystemEventData(
                subtype=line.get("subtype", "unknown"),
                duration_ms=line.get("durationMs"),
                hook_count=line.get("hookCount"),
                hook_infos=hook_infos,
                hook_errors=line.get("hookErrors"),
                prevented_continuation=line.get("preventedContinuation"),
                stop_reason=line.get("stopReason"),
            ),
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_queue_operation(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    content = line.get("content", "")
    task_id_match = re.search(r"<task-id>([^<]+)</task-id>", content)
    status_match = re.search(r"<status>([^<]+)</status>", content)
    summary_match = re.search(r"<summary>([^<]+)</summary>", content)
    output_match = re.search(r"<output-file>([^<]+)</output-file>", content)

    return [
        NormalizedMessage(
            id=f"queue-{(task_id_match.group(1) if task_id_match else line_num)}",
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="queue_operation",
            timestamp=line.get("timestamp", ""),
            content=content,
            queue_operation_data=QueueOperationData(
                operation=line.get("operation", "unknown"),
                task_id=task_id_match.group(1) if task_id_match else None,
                status=status_match.group(1) if status_match else None,
                summary=summary_match.group(1) if summary_match else None,
                output_file=output_match.group(1) if output_match else None,
            ),
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_file_snapshot(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    return [
        NormalizedMessage(
            id=line.get("uuid", f"snapshot-{line_num}"),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="file_snapshot",
            timestamp=line.get("timestamp", ""),
            raw_data=line,
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _transform_summary(
    line: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
) -> list[NormalizedMessage]:
    return [
        NormalizedMessage(
            id=line.get("uuid", f"summary-{line_num}"),
            session_id=session_id,
            source="claude_code",
            source_schema_version=1,
            msg_type="summary",
            timestamp=line.get("timestamp", ""),
            content=line.get("summary"),
            raw_data=line,
            raw_file_path=file_path,
            raw_line_number=line_num,
        )
    ]


def _extract_session_context(line: dict[str, Any]) -> SessionContext | None:
    ctx = line.get("sessionContext")
    if not isinstance(ctx, dict):
        return None
    return SessionContext(
        user_email=ctx.get("user_email"),
        user_name=ctx.get("user_name"),
        device_name=ctx.get("device_name"),
        device_id=ctx.get("device_id"),
        cwd=ctx.get("cwd"),
        repo_url=ctx.get("repo_url"),
        repo_name=ctx.get("repo_name"),
        git_branch=ctx.get("git_branch"),
        git_commit=ctx.get("git_commit"),
        project_hash=ctx.get("project_hash"),
        org=ctx.get("org"),
    )
