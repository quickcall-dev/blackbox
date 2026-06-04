# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Annotate normalized messages with user/system roles."""


import re

from src.normalizer.unified import NormalizedMessage

_USER_QUERY_RE = re.compile(r"<user_query[^>]*>(.*?)</user_query>", re.DOTALL)
_CURSOR_CONTEXT_TAGS = re.compile(
    r"<(?:open_and_recently_viewed_files|attached_files|code_selection|"
    r"user_info|rules|always_applied_workspace_rules?|agent_skill|"
    r"open_files|repo_map|file_map|codebase_search|recently_viewed_files)"
)
_CODEX_SYSTEM_RE = re.compile(
    r"<(?:INSTRUCTIONS|environment_context|cwd|shell|approval_policy|"
    r"sandbox_mode|network_access|collaboration_mode|permissions\s+instructions)>"
)
_GEMINI_SYSTEM_RE = re.compile(
    r"<(?:INSTRUCTIONS|environment_context|cwd|shell|approval_policy|"
    r"sandbox_mode|network_access|workspace_context|files_context)>"
)
_CC_COMMAND_RE = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)
_CC_SCAFFOLDING_RE = re.compile(
    r"<(?:local-command-caveat|local-command-stdout|task-notification|"
    r"task-id|command-name|system-reminder)>"
)


def _classify_user_message(text: str, source: str) -> tuple[str, str | None]:
    stripped = text.strip()

    if source in {"cursor", "cursor_vscdb"}:
        user_query = _USER_QUERY_RE.search(text)
        if user_query:
            extracted = user_query.group(1).strip()
            if extracted:
                return "real_user", extracted
            return "system_context", None
        if _CURSOR_CONTEXT_TAGS.search(text):
            return "system_context", None
        if stripped:
            return "real_user", stripped
        return "system_context", None

    if source == "codex_cli":
        if _CODEX_SYSTEM_RE.search(text):
            return "system_context", None
        if stripped:
            return "real_user", stripped
        return "system_context", None

    if source == "gemini_cli":
        if _GEMINI_SYSTEM_RE.search(text):
            return "system_context", None
        if stripped:
            return "real_user", stripped
        return "system_context", None

    if source == "claude_code":
        command = _CC_COMMAND_RE.search(text)
        if command:
            cmd_name = command.group(1).strip()
            if cmd_name in {"/clear", "clear", "/compact", "compact", "/init", "init"}:
                return "system_context", None
            return "system_context", None
        if _CC_SCAFFOLDING_RE.search(text):
            return "system_context", None
        if stripped:
            return "real_user", stripped
        return "system_context", None

    if source == "pi":
        if stripped:
            return "real_user", stripped
        return "system_context", None

    if stripped:
        return "real_user", stripped
    return "other", None


def annotate_unified(messages: list[NormalizedMessage]) -> dict:
    """Annotate normalized messages with user intent roles and turn counts."""

    annotated_messages = []
    real_user_turns = 0
    real_assistant_turns = 0
    has_tool_calls = False
    source = messages[0].source if messages else "unknown"

    for message in messages:
        role = "other"
        real_content = None
        turn_number = None
        text = message.content or ""

        if message.msg_type == "user":
            role, real_content = _classify_user_message(text, message.source)
            if role == "real_user":
                real_user_turns += 1
                turn_number = real_user_turns

        elif message.msg_type == "assistant":
            role = "assistant"
            if text.strip():
                real_assistant_turns += 1
                turn_number = real_assistant_turns
                real_content = text.strip()

        elif message.msg_type == "tool_call":
            role = "tool_call"
            has_tool_calls = True

        elif message.msg_type == "tool_result":
            role = "tool_result"

        elif message.msg_type in {"system", "system_event"}:
            role = "system_context"

        annotated_messages.append(
            {
                "msg_id": message.id,
                "msg_type": message.msg_type,
                "role": role,
                "real_content": real_content,
                "turn_number": turn_number,
            }
        )

    return {
        "messages": annotated_messages,
        "stats": {
            "real_user_turns": real_user_turns,
            "real_assistant_turns": real_assistant_turns,
            "total_messages": len(messages),
            "source": source,
            "has_tool_calls": has_tool_calls,
        },
    }
