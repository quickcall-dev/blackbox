# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Transform pi.dev JSONL session data to unified format."""


from typing import Any

from .unified import NormalizedMessage, TokenUsage, ToolCall, ToolResult


def normalize_pi(lines: list[dict], file_path: str = "") -> list[NormalizedMessage]:
    """Normalize a pi.dev session."""
    session_id = ""
    current_model: str | None = None
    messages: list[NormalizedMessage] = []

    for line_num, event in enumerate(lines, start=1):
        if event.get("type") == "session":
            session_id = event.get("id", session_id)
        elif event.get("type") == "model_change":
            current_model = event.get("model") or event.get("provider")
            continue
        messages.extend(transform_pi_v1(event, session_id, file_path, line_num, current_model=current_model))

    return messages


def _extract_text(content: list[dict]) -> str:
    texts = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n\n".join(texts) if texts else ""


def _extract_thinking(content: list[dict]) -> str:
    thoughts = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "thinking":
            thoughts.append(part.get("thinking", ""))
    return "\n\n".join(thoughts) if thoughts else ""


def _extract_tool_calls(
    content: list[dict],
    parent_id: str,
    session_id: str,
    timestamp: str,
    file_path: str,
    line_num: int,
    model: str | None,
) -> list[NormalizedMessage]:
    messages = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "toolCall":
            continue
        messages.append(
            NormalizedMessage(
                id=part.get("id", f"{parent_id}-tool"),
                session_id=session_id,
                source="pi",
                source_schema_version=1,
                msg_type="tool_call",
                timestamp=timestamp,
                tool_call=ToolCall(
                    id=part.get("id", ""),
                    name=part.get("name", ""),
                    input=part.get("arguments", {}),
                ),
                model=model,
                raw_file_path=file_path,
                raw_line_number=line_num,
            )
        )
    return messages


def _extract_tokens(usage: dict[str, Any]) -> TokenUsage:
    return TokenUsage(
        input=usage.get("input", 0),
        output=usage.get("output", 0),
        cached=usage.get("cacheRead", 0),
        thinking=usage.get("cacheWrite", 0),
    )


def transform_pi_v1(
    event: dict[str, Any],
    session_id: str,
    file_path: str,
    line_num: int,
    current_model: str | None = None,
) -> list[NormalizedMessage]:
    event_type = event.get("type")
    event_id = event.get("id", f"evt-{line_num}")
    timestamp = event.get("timestamp", "")

    if event_type in ("session", "thinking_level_change", "custom", "custom_message", "model_change"):
        return []

    if event_type == "compaction":
        return [
            NormalizedMessage(
                id=event_id,
                session_id=session_id,
                source="pi",
                source_schema_version=1,
                msg_type="compaction",
                timestamp=timestamp,
                content=event.get("summary"),
                raw_data=event,
                raw_file_path=file_path,
                raw_line_number=line_num,
            )
        ]

    if event_type != "message":
        return []

    msg = event.get("message", {})
    role = msg.get("role")
    if role == "user":
        content = msg.get("content", [])
        text = _extract_text(content) if isinstance(content, list) else str(content)
        return [
            NormalizedMessage(
                id=event_id,
                session_id=session_id,
                source="pi",
                source_schema_version=1,
                msg_type="user",
                timestamp=timestamp,
                content=text or None,
                raw_file_path=file_path,
                raw_line_number=line_num,
            )
        ]

    if role == "assistant":
        content = msg.get("content", [])
        text = _extract_text(content) if isinstance(content, list) else None
        thinking = _extract_thinking(content) if isinstance(content, list) else None
        usage = msg.get("usage", {})
        tokens = _extract_tokens(usage) if usage else TokenUsage()
        model = msg.get("model") or current_model
        messages: list[NormalizedMessage] = []
        if isinstance(content, list):
            messages.extend(_extract_tool_calls(content, event_id, session_id, timestamp, file_path, line_num, model))
        if text or thinking:
            messages.insert(
                0,
                NormalizedMessage(
                    id=event_id,
                    session_id=session_id,
                    source="pi",
                    source_schema_version=1,
                    msg_type="assistant",
                    timestamp=timestamp,
                    content=text or None,
                    tokens=tokens,
                    thinking=thinking or None,
                    model=model,
                    raw_file_path=file_path,
                    raw_line_number=line_num,
                ),
            )
        return messages

    if role == "toolResult":
        content = msg.get("content", [])
        text = _extract_text(content) if isinstance(content, list) else str(content)
        return [
            NormalizedMessage(
                id=event_id,
                session_id=session_id,
                source="pi",
                source_schema_version=1,
                msg_type="tool_result",
                timestamp=timestamp,
                tool_result=ToolResult(
                    call_id=msg.get("toolCallId", ""),
                    output=text,
                    status="failure" if msg.get("isError") else "success",
                ),
                raw_file_path=file_path,
                raw_line_number=line_num,
            )
        ]

    if role == "bashExecution":
        return []
    return []
