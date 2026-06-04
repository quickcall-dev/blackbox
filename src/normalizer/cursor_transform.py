# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Transform Cursor IDE transcript text to unified format."""


import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from .cursor_v1 import CursorAgentTranscript, CursorToolInvocation, CursorTranscriptMessage
from .unified import NormalizedMessage, ToolCall, ToolResult


def extract_session_id(file_path: str) -> str:
    match = re.search(r"/([^/]+)\.txt$", file_path)
    if match:
        return match.group(1)
    return file_path


def normalize_cursor_txt(text: str, file_path: str = "") -> list[NormalizedMessage]:
    """Normalize Cursor transcript text content."""
    transcript: CursorAgentTranscript = {
        "composer_id": extract_session_id(file_path) if file_path else "",
        "file_path": file_path,
        "messages": _parse_transcript_content(text),
        "raw_content": text,
    }
    return transform_cursor_v1(transcript, file_path)


def transform_cursor_v1(transcript: CursorAgentTranscript, file_path: str) -> list[NormalizedMessage]:
    session_id = transcript.get("composer_id") or extract_session_id(file_path)
    messages: list[NormalizedMessage] = []
    msg_index = 0
    base_dt: datetime | None = None
    if file_path:
        try:
            base_dt = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
        except OSError:
            base_dt = None

    for msg in transcript.get("messages", []):
        result = transform_transcript_message(msg, session_id, file_path, msg_index, base_dt)
        messages.extend(result)
        msg_index += len(result)
    return messages


def transform_transcript_message(
    msg: CursorTranscriptMessage,
    session_id: str,
    file_path: str,
    msg_index: int,
    base_dt: datetime | None = None,
) -> list[NormalizedMessage]:
    role = msg.get("role", "user")
    file_ts = _sequential_ts(base_dt, msg_index) if base_dt else ""
    if role == "user":
        return [_transform_user_message(msg, session_id, file_path, msg_index, file_ts)]
    return _transform_assistant_message(msg, session_id, file_path, msg_index, base_dt)


def _transform_user_message(
    msg: CursorTranscriptMessage,
    session_id: str,
    file_path: str,
    msg_index: int,
    file_ts: str = "",
) -> NormalizedMessage:
    return NormalizedMessage(
        id=f"{session_id}-{msg_index}",
        session_id=session_id,
        source="cursor",
        source_schema_version=1,
        msg_type="user",
        timestamp=file_ts,
        content=msg.get("content", ""),
        raw_file_path=file_path,
    )


def _transform_assistant_message(
    msg: CursorTranscriptMessage,
    session_id: str,
    file_path: str,
    msg_index: int,
    base_dt: datetime | None = None,
) -> list[NormalizedMessage]:
    messages: list[NormalizedMessage] = []
    content = msg.get("content", "")
    thinking = msg.get("thinking")
    tool_calls = msg.get("tool_calls", [])
    sub_offset = 0

    if content or thinking:
        ts = _sequential_ts(base_dt, msg_index + sub_offset) if base_dt else ""
        messages.append(
            NormalizedMessage(
                id=f"{session_id}-{msg_index}",
                session_id=session_id,
                source="cursor",
                source_schema_version=1,
                msg_type="assistant",
                timestamp=ts,
                content=content if content else None,
                thinking=thinking,
                raw_file_path=file_path,
            )
        )
        sub_offset += 1

    last_call_id: str | None = None
    for tool in tool_calls:
        ts = _sequential_ts(base_dt, msg_index + sub_offset) if base_dt else ""
        tool_messages = transform_tool_invocation(
            tool,
            session_id,
            file_path,
            msg_index + sub_offset,
            ts,
            preceding_call_id=last_call_id,
        )
        messages.extend(tool_messages)
        sub_offset += len(tool_messages)
        if tool.get("type", "tool_call") == "tool_call":
            last_call_id = f"{session_id}-tool-{msg_index + sub_offset - 1}"
        else:
            last_call_id = None

    return messages


def transform_tool_invocation(
    tool: CursorToolInvocation,
    session_id: str,
    file_path: str,
    msg_index: int,
    file_ts: str = "",
    preceding_call_id: str | None = None,
) -> list[NormalizedMessage]:
    tool_type = tool.get("type", "tool_call")
    tool_name = tool.get("tool_name", "")
    tool_id = f"{session_id}-tool-{msg_index}"

    if tool_type == "tool_call":
        return [
            NormalizedMessage(
                id=tool_id,
                session_id=session_id,
                source="cursor",
                source_schema_version=1,
                msg_type="tool_call",
                timestamp=file_ts,
                tool_call=ToolCall(
                    id=tool_id,
                    name=tool_name,
                    input=tool.get("parameters", {}),
                ),
                raw_file_path=file_path,
            )
        ]

    return [
        NormalizedMessage(
            id=tool_id,
            session_id=session_id,
            source="cursor",
            source_schema_version=1,
            msg_type="tool_result",
            timestamp=file_ts,
            tool_result=ToolResult(
                call_id=preceding_call_id or tool_id,
                output=tool.get("result") or "",
                status="success",
            ),
            raw_file_path=file_path,
        )
    ]


def _sequential_ts(base_dt: datetime, offset: int) -> str:
    return (base_dt + timedelta(milliseconds=offset)).isoformat()


def transform_composer_metadata(composer: dict, file_path: str) -> NormalizedMessage:
    composer_id = composer.get("composerId", str(uuid.uuid4()))
    created_at = composer.get("createdAt")
    timestamp = ""
    if created_at:
        timestamp = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
    return NormalizedMessage(
        id=f"{composer_id}-meta",
        session_id=composer_id,
        source="cursor",
        source_schema_version=1,
        msg_type="system",
        timestamp=timestamp,
        content=f"Cursor {composer.get('unifiedMode', 'chat')} session: {composer.get('name', 'Untitled')}",
        raw_data=dict(composer),
        raw_file_path=file_path,
    )


def _parse_transcript_content(content: str) -> list[CursorTranscriptMessage]:
    messages: list[CursorTranscriptMessage] = []
    parts = re.compile(r"^(user|assistant):\s*$", re.MULTILINE).split(content)
    i = 1
    while i < len(parts) - 1:
        role = parts[i].strip()
        msg_content = parts[i + 1] if i + 1 < len(parts) else ""
        if role == "user":
            messages.append(_parse_user_message(msg_content))
        elif role == "assistant":
            messages.append(_parse_assistant_message(msg_content))
        i += 2
    return messages


def _parse_user_message(content: str) -> CursorTranscriptMessage:
    query_match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", content, re.DOTALL)
    extracted = query_match.group(1).strip() if query_match else content.strip()
    return {"role": "user", "content": extracted, "thinking": None, "tool_calls": []}


def _parse_assistant_message(content: str) -> CursorTranscriptMessage:
    thinking = None
    think_match = re.search(r"<think>\s*(.*?)\s*</think>", content, re.DOTALL)
    if think_match:
        thinking = think_match.group(1).strip()
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    tool_calls = _extract_tool_invocations(content)
    clean_content = _remove_tool_sections(content).strip()
    return {
        "role": "assistant",
        "content": clean_content,
        "thinking": thinking,
        "tool_calls": tool_calls,
    }


def _extract_tool_invocations(content: str) -> list[CursorToolInvocation]:
    tool_calls: list[CursorToolInvocation] = []
    tool_call_pattern = re.compile(r"\[Tool call\]\s+(\w+)\s*\n((?:[ \t]+\w+:.*\n?)*)", re.MULTILINE)
    for match in tool_call_pattern.finditer(content):
        parameters = {}
        for line in match.group(2).strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                parameters[key.strip()] = value.strip()
        tool_calls.append(
            {
                "type": "tool_call",
                "tool_name": match.group(1),
                "parameters": parameters,
                "result": None,
            }
        )

    tool_result_pattern = re.compile(
        r"\[Tool result\]\s+(\w+)\s*\n?(.*?)(?=\[Tool (?:call|result)\]|assistant:|user:|$)",
        re.DOTALL,
    )
    for match in tool_result_pattern.finditer(content):
        tool_calls.append(
            {
                "type": "tool_result",
                "tool_name": match.group(1),
                "parameters": {},
                "result": match.group(2).strip() or None,
            }
        )
    return tool_calls


def _remove_tool_sections(content: str) -> str:
    content = re.sub(r"\[Tool call\]\s+\w+\s*\n(?:[ \t]+\w+:.*\n?)*", "", content, flags=re.MULTILINE)
    content = re.sub(
        r"\[Tool result\]\s+\w+\s*\n?.*?(?=\[Tool (?:call|result)\]|assistant:|user:|$)",
        "",
        content,
        flags=re.DOTALL,
    )
    return content
