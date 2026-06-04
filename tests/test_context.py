# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for dedup, context builder, and user message extraction."""

import pytest
from src.pipeline.dedup import dedup_annotated_messages
from src.pipeline.context_builder import build_context_window, format_context_for_prompt, context_stats, extract_user_messages


def test_dedup_removes_consecutive_duplicate_user_messages():
    annotated = {"messages": [
        {"msg_id": "m1", "role": "real_user", "real_content": "hello"},
        {"msg_id": "m2", "role": "real_user", "real_content": "hello"},
        {"msg_id": "m3", "role": "assistant", "real_content": "hi"},
    ], "stats": {}}
    result = dedup_annotated_messages(annotated)
    assert len(result["messages"]) == 2
    assert result["messages"][0]["msg_id"] == "m1"
    assert result["messages"][1]["msg_id"] == "m3"
    assert result["stats"]["duplicates_removed"] == 1


def test_dedup_keeps_non_consecutive_duplicates():
    annotated = {"messages": [
        {"msg_id": "m1", "role": "real_user", "real_content": "hello"},
        {"msg_id": "m2", "role": "assistant", "real_content": "hi"},
        {"msg_id": "m3", "role": "real_user", "real_content": "hello"},
    ], "stats": {}}
    result = dedup_annotated_messages(annotated)
    assert len(result["messages"]) == 3


def test_dedup_does_not_dedup_assistant_messages():
    annotated = {"messages": [
        {"msg_id": "m1", "role": "assistant", "real_content": "hi"},
        {"msg_id": "m2", "role": "assistant", "real_content": "hi"},
    ], "stats": {}}
    result = dedup_annotated_messages(annotated)
    assert len(result["messages"]) == 2


def test_extract_user_messages_filters_and_orders():
    annotated = {"messages": [
        {"role": "system_context", "real_content": "scaffold", "turn_number": None},
        {"role": "real_user", "real_content": "hello", "turn_number": 1},
        {"role": "assistant", "real_content": "hi", "turn_number": 1},
        {"role": "real_user", "real_content": "fix this", "turn_number": 2},
    ]}
    user_msgs = extract_user_messages(annotated)
    assert len(user_msgs) == 2
    assert user_msgs[0]["text"] == "hello"
    assert user_msgs[0]["turn_index"] == 1
    assert user_msgs[1]["text"] == "fix this"
    assert user_msgs[1]["turn_index"] == 3


def test_extract_user_messages_skips_empty():
    annotated = {"messages": [
        {"role": "real_user", "real_content": "", "turn_number": 1},
        {"role": "real_user", "real_content": "valid", "turn_number": 2},
    ]}
    user_msgs = extract_user_messages(annotated)
    assert len(user_msgs) == 1
    assert user_msgs[0]["text"] == "valid"


def test_build_context_window_around_trigger():
    annotated = {"messages": [
        {"msg_id": f"m{i}", "role": "real_user" if i % 2 == 0 else "assistant",
         "real_content": f"msg{i}", "turn_number": i // 2 + 1}
        for i in range(20)
    ]}
    window = build_context_window(annotated, trigger_turn=10, before=5, after=3)
    turns = [m["original_turn"] for m in window]
    assert 10 in turns
    assert min(turns) == 5
    assert max(turns) == 13


def test_build_context_window_clamps_start():
    annotated = {"messages": [
        {"msg_id": f"m{i}", "role": "real_user" if i % 2 == 0 else "assistant",
         "real_content": f"msg{i}", "turn_number": i // 2 + 1}
        for i in range(20)
    ]}
    window = build_context_window(annotated, trigger_turn=2, before=5, after=3)
    turns = [m["original_turn"] for m in window]
    assert min(turns) == 0


def test_build_context_window_skips_empty():
    annotated = {"messages": [
        {"msg_id": "m1", "role": "real_user", "real_content": "hello", "turn_number": 1},
        {"msg_id": "m2", "role": "assistant", "real_content": "", "turn_number": 1},
        {"msg_id": "m3", "role": "real_user", "real_content": "fix", "turn_number": 2},
    ]}
    window = build_context_window(annotated, trigger_turn=2, before=2, after=1)
    contents = [m["content"] for m in window]
    assert "" not in contents


def test_format_context_for_prompt():
    context = [
        {"original_turn": 5, "role": "real_user", "content": "hello"},
        {"original_turn": 6, "role": "assistant", "content": "hi there"},
    ]
    formatted = format_context_for_prompt(context)
    assert "[Turn 5] [real_user] hello" in formatted
    assert "[Turn 6] [assistant] hi there" in formatted


def test_context_stats():
    context = [
        {"original_turn": 5, "role": "real_user", "content": "hello", "content_len": 5},
        {"original_turn": 6, "role": "assistant", "content": "hi there", "content_len": 8},
    ]
    stats = context_stats(context)
    assert stats["total"] == 2
    assert stats["by_role"]["real_user"] == 1
    assert stats["by_role"]["assistant"] == 1
    assert stats["total_chars"] == 13
    assert stats["turn_range"] == [5, 6]
