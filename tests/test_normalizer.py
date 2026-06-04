# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for normalizer transforms."""

import pytest

from src.normalizer.unified import NormalizedMessage, TokenUsage
from src.normalizer.claude_code_transform import normalize_claude_code
from src.normalizer.codex_cli_transform import normalize_codex_cli


def test_normalize_claude_code_basic():
    lines = [
        {
            "type": "user",
            "uuid": "u1",
            "sessionId": "s1",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {"content": "hello"},
        },
        {
            "type": "assistant",
            "uuid": "a1",
            "sessionId": "s1",
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        },
    ]
    messages = normalize_claude_code(lines)
    assert len(messages) == 2
    assert messages[0].msg_type == "user"
    assert messages[0].content == "hello"
    assert messages[1].msg_type == "assistant"
    assert messages[1].content == "hi"
    assert messages[1].tokens.input == 10
    assert messages[1].tokens.output == 5


def test_normalize_claude_code_with_tool_call():
    lines = [
        {
            "type": "assistant",
            "uuid": "a1",
            "sessionId": "s1",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "I'll read that"},
                    {"type": "tool_use", "id": "tool1", "name": "Read", "input": {"file_path": "test.py"}},
                ],
                "usage": {"input_tokens": 5, "output_tokens": 5},
            },
        },
    ]
    messages = normalize_claude_code(lines)
    assert len(messages) == 2
    assert messages[0].msg_type == "assistant"
    assert messages[1].msg_type == "tool_call"
    assert messages[1].tool_call.name == "Read"


def test_normalize_codex_cli_basic():
    lines = [
        {"type": "session_meta", "payload": {"id": "s1"}},
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "hello"},
            "timestamp": "2026-01-01T00:00:00Z",
        },
        {
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "hi"},
            "timestamp": "2026-01-01T00:00:01Z",
        },
    ]
    messages = normalize_codex_cli(lines)
    assert len(messages) == 2
    assert messages[0].msg_type == "user"
    assert messages[0].content == "hello"
    assert messages[1].msg_type == "assistant"
    assert messages[1].content == "hi"


def test_normalize_codex_cli_with_tool_call():
    lines = [
        {"type": "session_meta", "payload": {"id": "s1"}},
        {
            "type": "response_item",
            "payload": {"type": "function_call", "call_id": "c1", "name": "bash", "arguments": "{}"},
            "timestamp": "2026-01-01T00:00:00Z",
        },
        {
            "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": "c1", "output": "output"},
            "timestamp": "2026-01-01T00:00:01Z",
        },
    ]
    messages = normalize_codex_cli(lines)
    assert len(messages) == 2
    assert messages[0].msg_type == "tool_call"
    assert messages[0].tool_call.name == "bash"
    assert messages[1].msg_type == "tool_result"
    assert messages[1].tool_result.call_id == "c1"
