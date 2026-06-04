# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Cursor transcript parser types."""


from typing import Literal, TypedDict


class CursorToolInvocation(TypedDict, total=False):
    type: Literal["tool_call", "tool_result"]
    tool_name: str
    parameters: dict[str, str]
    result: str | None


class CursorTranscriptMessage(TypedDict, total=False):
    role: Literal["user", "assistant"]
    content: str
    thinking: str | None
    tool_calls: list[CursorToolInvocation]


class CursorAgentTranscript(TypedDict, total=False):
    composer_id: str
    file_path: str
    messages: list[CursorTranscriptMessage]
    raw_content: str | None


class CursorTerminalSession(TypedDict, total=False):
    session_id: str
    file_path: str
    pid: int | None
    cwd: str | None
    content: str
