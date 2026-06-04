# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Transform Cursor state.vscdb sessions to unified format."""


import json
from datetime import datetime, timezone
from typing import Any, Literal

from .unified import NormalizedMessage, SessionContext, TokenUsage, ToolCall, ToolResult
from .vscdb_reader import VscdbSession, _decompress, _extract_hashes, iter_sessions


def normalize_cursor_vscdb(db_path: str) -> list[NormalizedMessage]:
    """Normalize all Cursor sessions found in a state.vscdb database."""
    messages: list[NormalizedMessage] = []
    for session in iter_sessions(db_path):
        messages.extend(transform_cursor_vscdb(session))
    return messages


def transform_cursor_vscdb(session: VscdbSession) -> list[NormalizedMessage]:
    mode = _detect_mode(session.composer_data)
    if mode == "inline":
        return _transform_inline(session)
    if mode == "hashchain":
        messages = _transform_hashchain(session)
        if not messages:
            headers = session.composer_data.get("fullConversationHeadersOnly")
            if headers and isinstance(headers, list):
                return _transform_headers_only(session)
        return messages
    return _transform_headers_only(session)


def _detect_mode(cd: dict) -> Literal["inline", "hashchain", "headers_only"]:
    if cd.get("conversation") and isinstance(cd["conversation"], list):
        for bubble in cd["conversation"]:
            if isinstance(bubble, dict) and bubble.get("text"):
                return "inline"
    if cd.get("conversationState") and isinstance(cd["conversationState"], str):
        return "hashchain"
    if cd.get("fullConversationHeadersOnly") and isinstance(cd["fullConversationHeadersOnly"], list):
        return "headers_only"
    if cd.get("conversation"):
        return "headers_only"
    return "headers_only"


def _transform_inline(session: VscdbSession) -> list[NormalizedMessage]:
    messages: list[NormalizedMessage] = []
    cd = session.composer_data
    fallback_ts = _ms_to_iso(cd.get("createdAt", 0))
    model = _extract_model(cd)
    session_context = _extract_session_context(cd)

    for i, bubble in enumerate(cd.get("conversation", [])):
        if not isinstance(bubble, dict):
            continue
        bubble_type = bubble.get("type", 0)
        bubble_id = bubble.get("bubbleId", "")
        text = bubble.get("text", "")
        timing = bubble.get("timingInfo") or {}
        is_capability = bubble.get("isCapabilityIteration", False) or bubble.get("capabilityType") is not None
        capability_type = bubble.get("capabilityType", "")
        client_start = timing.get("clientStartTime")
        ts = _ms_to_iso(client_start) if client_start else fallback_ts
        tokens = _bubble_tokens(session, session.composer_id, bubble_id)

        thinking = None
        thinking_blocks = bubble.get("allThinkingBlocks", [])
        if thinking_blocks:
            parts = [tb["thinking"] for tb in thinking_blocks if isinstance(tb, dict) and tb.get("thinking")]
            if parts:
                thinking = "\n\n".join(parts)

        msg_id = f"{session.composer_id}-{i}"
        if is_capability:
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="tool_call",
                    timestamp=ts,
                    content=text if text else None,
                    tokens=tokens,
                    tool_call=ToolCall(id=msg_id, name=str(capability_type) if capability_type else "unknown", input={}),
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
        elif bubble_type == 1:
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="user",
                    timestamp=ts if not client_start else fallback_ts,
                    content=text if text else None,
                    tokens=tokens,
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
        elif bubble_type == 2:
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="assistant",
                    timestamp=ts,
                    content=text if text else None,
                    tokens=tokens,
                    thinking=thinking,
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
    return messages


def _transform_hashchain(session: VscdbSession) -> list[NormalizedMessage]:
    messages: list[NormalizedMessage] = []
    cd = session.composer_data
    fallback_ts = _ms_to_iso(cd.get("createdAt", 0))
    model = _extract_model(cd)
    session_context = _extract_session_context(cd)

    for i, hash_value in enumerate(_extract_hashes(cd.get("conversationState", ""))):
        raw = session.agent_kv_entries.get(f"agentKv:blob:{hash_value}")
        if raw is None:
            continue
        parsed = _parse_agent_kv_json(raw)
        if parsed is None:
            continue

        role = parsed.get("role", "")
        msg_id = f"{session.composer_id}-hc-{i}"
        if role == "user":
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="user",
                    timestamp=fallback_ts,
                    content=_extract_text_from_content(parsed.get("content", [])),
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
        elif role == "assistant":
            content_parts = parsed.get("content", [])
            text = _extract_text_from_content(content_parts)
            if text:
                messages.append(
                    NormalizedMessage(
                        id=msg_id,
                        session_id=session.composer_id,
                        source="cursor_vscdb",
                        source_schema_version=2,
                        msg_type="assistant",
                        timestamp=fallback_ts,
                        content=text,
                        model=model,
                        session_context=session_context,
                        raw_file_path=session.db_path,
                    )
                )
            for j, tool_call in enumerate(_extract_tool_calls_from_content(content_parts, msg_id)):
                messages.append(
                    NormalizedMessage(
                        id=f"{msg_id}-tc-{j}",
                        session_id=session.composer_id,
                        source="cursor_vscdb",
                        source_schema_version=2,
                        msg_type="tool_call",
                        timestamp=fallback_ts,
                        tool_call=tool_call,
                        model=model,
                        session_context=session_context,
                        raw_file_path=session.db_path,
                    )
                )
        elif role == "tool":
            content_parts = parsed.get("content", [])
            status: Literal["success", "failure"] = "success"
            provider = parsed.get("providerOptions", {})
            cursor_opts = provider.get("cursor", {}) if isinstance(provider, dict) else {}
            high_level = cursor_opts.get("highLevelToolCallResult", {}) if isinstance(cursor_opts, dict) else {}
            if isinstance(high_level, dict) and high_level.get("isError"):
                status = "failure"
            elif isinstance(content_parts, list):
                for part in content_parts:
                    if isinstance(part, dict) and (part.get("is_error") or part.get("isError")):
                        status = "failure"
                        break
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="tool_result",
                    timestamp=fallback_ts,
                    tool_result=ToolResult(
                        call_id=parsed.get("id") or parsed.get("tool_call_id") or msg_id,
                        output=_extract_text_from_content(content_parts) or "",
                        status=status,
                    ),
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
    return messages


def _transform_headers_only(session: VscdbSession) -> list[NormalizedMessage]:
    messages: list[NormalizedMessage] = []
    cd = session.composer_data
    fallback_ts = _ms_to_iso(cd.get("createdAt", 0))
    model = _extract_model(cd)
    session_context = _extract_session_context(cd)
    headers = cd.get("fullConversationHeadersOnly") or cd.get("conversation") or []

    for i, bubble in enumerate(headers):
        if not isinstance(bubble, dict):
            continue
        bubble_type = bubble.get("type", 0)
        bubble_id = bubble.get("bubbleId", "")
        is_capability = bubble.get("isCapabilityIteration", False) or bubble.get("capabilityType") is not None
        tokens = _bubble_tokens(session, session.composer_id, bubble_id)
        bubble_entry = session.bubble_entries.get(f"bubbleId:{session.composer_id}:{bubble_id}")
        ts = _ms_to_iso(bubble_entry["createdAt"]) if bubble_entry and bubble_entry.get("createdAt") else fallback_ts
        content = bubble_entry.get("text") or None if bubble_entry else None
        thinking = None
        if bubble_entry and bubble_type == 2:
            blocks = bubble_entry.get("allThinkingBlocks") or []
            thinking = "\n".join(b.get("thinking", "") for b in blocks if b.get("thinking")) or None
        msg_id = f"{session.composer_id}-ho-{i}"
        if is_capability:
            capability_type = bubble.get("capabilityType", "unknown")
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="tool_call",
                    timestamp=ts,
                    tokens=tokens,
                    content=content,
                    tool_call=ToolCall(id=msg_id, name=str(capability_type) if capability_type else "unknown", input={}),
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
        elif bubble_type == 1:
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="user",
                    timestamp=ts,
                    tokens=tokens,
                    content=content,
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
        elif bubble_type == 2:
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session.composer_id,
                    source="cursor_vscdb",
                    source_schema_version=2,
                    msg_type="assistant",
                    timestamp=ts,
                    tokens=tokens,
                    content=content,
                    thinking=thinking,
                    model=model,
                    session_context=session_context,
                    raw_file_path=session.db_path,
                )
            )
    return messages


def _extract_model(cd: dict) -> str | None:
    mc = cd.get("modelConfig")
    if isinstance(mc, dict):
        return mc.get("modelName")
    return None


def _extract_session_context(cd: dict) -> SessionContext | None:
    repo_name = cd.get("workspaceName") or cd.get("name")
    git_branch = cd.get("createdOnBranch")
    if not any([repo_name, git_branch]):
        return None
    return SessionContext(repo_name=repo_name, git_branch=git_branch)


def _ms_to_iso(ms: int | str) -> str:
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (OSError, ValueError, OverflowError):
        return ""


def _bubble_tokens(session: VscdbSession, composer_id: str, bubble_id: str) -> TokenUsage:
    if not bubble_id:
        return TokenUsage()
    entry = session.bubble_entries.get(f"bubbleId:{composer_id}:{bubble_id}")
    if not entry:
        return TokenUsage()
    tc = entry.get("tokenCount")
    if not isinstance(tc, dict):
        return TokenUsage()
    return TokenUsage(input=tc.get("inputTokens", 0), output=tc.get("outputTokens", 0))


def _parse_agent_kv_json(raw: bytes) -> dict | None:
    try:
        parsed = json.loads(_decompress(raw).decode("utf-8", errors="replace"))
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass
    return None


def _extract_text_from_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content or None
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
            elif block.get("type") == "tool-result" and block.get("result"):
                parts.append(block["result"])
    return "\n".join(parts) if parts else None


def _extract_tool_calls_from_content(content: Any, parent_id: str) -> list[ToolCall]:
    if not isinstance(content, list):
        return []
    calls = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            calls.append(ToolCall(id=block.get("id", parent_id), name=block.get("name", "unknown"), input=block.get("input", {})))
        elif block.get("type") == "tool-call":
            calls.append(
                ToolCall(
                    id=block.get("toolCallId", parent_id),
                    name=block.get("toolName", "unknown"),
                    input=block.get("args", {}),
                )
            )
    return calls
