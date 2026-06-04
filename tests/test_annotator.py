# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for unified annotator."""

from src.pipeline.annotator import annotate_unified
from src.normalizer.unified import NormalizedMessage


def test_annotator_detects_system_scaffolding_claude():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="claude_code",
            msg_type="user",
            content="<command-name>/clear</command-name>",
            timestamp="",
        ),
        NormalizedMessage(
            id="m2",
            session_id="s1",
            source="claude_code",
            msg_type="user",
            content="implement this",
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["messages"][0]["role"] == "system_context"
    assert annotated["messages"][1]["role"] == "real_user"


def test_annotator_detects_system_scaffolding_codex():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="codex_cli",
            msg_type="user",
            content="<INSTRUCTIONS>do this</INSTRUCTIONS>",
            timestamp="",
        ),
        NormalizedMessage(
            id="m2",
            session_id="s1",
            source="codex_cli",
            msg_type="user",
            content="hello",
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["messages"][0]["role"] == "system_context"
    assert annotated["messages"][1]["role"] == "real_user"


def test_annotator_detects_system_scaffolding_cursor():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="cursor",
            msg_type="user",
            content="<user_query></user_query><open_files>...</open_files>",
            timestamp="",
        ),
        NormalizedMessage(
            id="m2",
            session_id="s1",
            source="cursor",
            msg_type="user",
            content="<user_query>fix bug</user_query>",
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["messages"][0]["role"] == "system_context"
    assert annotated["messages"][1]["role"] == "real_user"


def test_annotator_counts_turns():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="claude_code",
            msg_type="user",
            content="hello",
            timestamp="",
        ),
        NormalizedMessage(
            id="m2",
            session_id="s1",
            source="claude_code",
            msg_type="assistant",
            content="hi",
            timestamp="",
        ),
        NormalizedMessage(
            id="m3",
            session_id="s1",
            source="claude_code",
            msg_type="user",
            content="fix this",
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["stats"]["real_user_turns"] == 2
    assert annotated["stats"]["real_assistant_turns"] == 1


def test_annotator_preserves_assistant_messages():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="claude_code",
            msg_type="assistant",
            content="I'll help",
            timestamp="",
        ),
        NormalizedMessage(
            id="m2",
            session_id="s1",
            source="claude_code",
            msg_type="tool_call",
            content=None,
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["messages"][0]["role"] == "assistant"
    assert annotated["messages"][1]["role"] == "tool_call"
    assert annotated["stats"]["has_tool_calls"] is True


def test_annotator_empty_content_becomes_system_context():
    messages = [
        NormalizedMessage(
            id="m1",
            session_id="s1",
            source="claude_code",
            msg_type="user",
            content="",
            timestamp="",
        ),
    ]
    annotated = annotate_unified(messages)
    assert annotated["messages"][0]["role"] == "system_context"
