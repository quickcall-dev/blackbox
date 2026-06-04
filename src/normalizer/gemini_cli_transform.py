# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Transform Gemini CLI session data to unified format."""


from typing import Any

from .unified import NormalizedMessage, TokenUsage, ToolCall, ToolResult


def normalize_gemini(lines: list[dict], file_path: str = "") -> list[NormalizedMessage]:
    """Normalize Gemini CLI session data."""
    if len(lines) == 1 and isinstance(lines[0], dict) and "messages" in lines[0]:
        return transform_gemini_v1(lines[0], file_path)
    session = {
        "sessionId": lines[0].get("sessionId", "") if lines else "",
        "messages": lines,
    }
    return transform_gemini_v1(session, file_path)


def extract_tokens(tokens: dict[str, Any] | None) -> TokenUsage:
    if not tokens:
        return TokenUsage()
    return TokenUsage(
        input=tokens.get("input", 0),
        output=tokens.get("output", 0),
        cached=tokens.get("cached", 0),
        thinking=tokens.get("thoughts", 0),
    )


def extract_thoughts(thoughts: list[dict[str, Any]]) -> str | None:
    if not thoughts:
        return None
    parts = []
    for thought in thoughts:
        subject = thought.get("subject", "")
        description = thought.get("description", "")
        if subject and description:
            parts.append(f"**{subject}**: {description}")
        elif description:
            parts.append(description)
        elif subject:
            parts.append(subject)
    return "\n\n".join(parts) if parts else None


def transform_gemini_v1(session: dict[str, Any], file_path: str) -> list[NormalizedMessage]:
    session_id = session.get("sessionId", "")
    normalized: list[NormalizedMessage] = []
    for msg in session.get("messages", []):
        normalized.extend(_transform_message(msg, session_id, file_path))
    return normalized


def _transform_message(msg: dict[str, Any], session_id: str, file_path: str) -> list[NormalizedMessage]:
    msg_type = msg.get("type")
    if msg_type == "user":
        return [_transform_user_message(msg, session_id, file_path)]
    if msg_type == "gemini":
        return _transform_gemini_message(msg, session_id, file_path)
    if msg_type == "error":
        return [_transform_error_message(msg, session_id, file_path)]
    if msg_type == "info":
        return [_transform_info_message(msg, session_id, file_path)]
    if msg_type == "warning":
        return [_transform_warning_message(msg, session_id, file_path)]
    return []


def _transform_user_message(msg: dict[str, Any], session_id: str, file_path: str) -> NormalizedMessage:
    return NormalizedMessage(
        id=msg.get("id", ""),
        session_id=session_id,
        source="gemini_cli",
        source_schema_version=1,
        msg_type="user",
        timestamp=msg.get("timestamp", ""),
        content=msg.get("content"),
        raw_file_path=file_path,
    )


def _transform_gemini_message(msg: dict[str, Any], session_id: str, file_path: str) -> list[NormalizedMessage]:
    messages = [
        NormalizedMessage(
            id=msg.get("id", ""),
            session_id=session_id,
            source="gemini_cli",
            source_schema_version=1,
            msg_type="assistant",
            timestamp=msg.get("timestamp", ""),
            content=msg.get("content"),
            tokens=extract_tokens(msg.get("tokens")),
            thinking=extract_thoughts(msg.get("thoughts", [])),
            model=msg.get("model"),
            raw_file_path=file_path,
        )
    ]

    for tc in msg.get("toolCalls", []):
        messages.append(
            NormalizedMessage(
                id=tc.get("id", ""),
                session_id=session_id,
                source="gemini_cli",
                source_schema_version=1,
                msg_type="tool_call",
                timestamp=tc.get("timestamp", msg.get("timestamp", "")),
                tool_call=ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    input=tc.get("args", {}),
                ),
                raw_file_path=file_path,
            )
        )

        result = tc.get("result", [])
        result_display = tc.get("resultDisplay")
        status = tc.get("status", "success")
        if result or result_display:
            output = ""
            if isinstance(result_display, str):
                output = result_display
            elif isinstance(result_display, dict):
                output = result_display.get("output", "") or result_display.get("error", "") or result_display.get("newContent", "")
            if not output and result:
                for item in result:
                    if not isinstance(item, dict):
                        continue
                    response = item.get("functionResponse", {}).get("response", {})
                    if "output" in response:
                        output = response["output"]
                        break
                    if "error" in response:
                        output = response["error"]
                        break
            messages.append(
                NormalizedMessage(
                    id=f"{tc.get('id', '')}-result",
                    session_id=session_id,
                    source="gemini_cli",
                    source_schema_version=1,
                    msg_type="tool_result",
                    timestamp=tc.get("timestamp", msg.get("timestamp", "")),
                    tool_result=ToolResult(
                        call_id=tc.get("id", ""),
                        output=str(output),
                        status="failure" if status in ("error", "cancelled") else "success",
                    ),
                    raw_file_path=file_path,
                )
            )
    return messages


def _transform_error_message(msg: dict[str, Any], session_id: str, file_path: str) -> NormalizedMessage:
    return NormalizedMessage(
        id=msg.get("id", ""),
        session_id=session_id,
        source="gemini_cli",
        source_schema_version=1,
        msg_type="error",
        timestamp=msg.get("timestamp", ""),
        content=msg.get("content"),
        raw_file_path=file_path,
    )


def _transform_info_message(msg: dict[str, Any], session_id: str, file_path: str) -> NormalizedMessage:
    return NormalizedMessage(
        id=msg.get("id", ""),
        session_id=session_id,
        source="gemini_cli",
        source_schema_version=1,
        msg_type="info",
        timestamp=msg.get("timestamp", ""),
        content=msg.get("content"),
        raw_file_path=file_path,
    )


def _transform_warning_message(msg: dict[str, Any], session_id: str, file_path: str) -> NormalizedMessage:
    return NormalizedMessage(
        id=msg.get("id", ""),
        session_id=session_id,
        source="gemini_cli",
        source_schema_version=1,
        msg_type="info",
        timestamp=msg.get("timestamp", ""),
        content=msg.get("content"),
        raw_file_path=file_path,
    )
