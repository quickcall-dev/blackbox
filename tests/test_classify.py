# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for message classification."""

import pytest
from src.classify.prompts import CLASSIFICATION_SCHEMA, CLASSIFICATION_SYSTEM_PROMPT
from src.classify.runner import (
    build_classification_prompt,
    get_rca_triggers,
    get_session_skeleton,
    parse_classifications,
)


def test_build_classification_prompt():
    user_msgs = [
        {"turn_index": 0, "text": "hello"},
        {"turn_index": 2, "text": "fix bug"},
    ]
    prompt = build_classification_prompt(user_msgs)
    assert "[Turn 0] hello" in prompt
    assert "[Turn 2] fix bug" in prompt
    assert "Classify each user message" in prompt


def test_parse_classifications_merges_with_messages():
    response = [
        {"turn": 0, "label": "new_task"},
        {"turn": 2, "label": "correction"},
    ]
    user_msgs = [
        {"turn_index": 0, "text": "hello"},
        {"turn_index": 2, "text": "fix bug"},
    ]
    classified = parse_classifications(response, user_msgs)
    assert len(classified) == 2
    assert classified[0]["label"] == "new_task"
    assert classified[0]["text"] == "hello"
    assert classified[1]["label"] == "correction"
    assert classified[1]["text"] == "fix bug"


def test_parse_classifications_adds_missing_as_other():
    response = [{"turn": 0, "label": "new_task"}]
    user_msgs = [
        {"turn_index": 0, "text": "hello"},
        {"turn_index": 1, "text": "ok"},
    ]
    classified = parse_classifications(response, user_msgs)
    assert len(classified) == 2
    assert classified[1]["label"] == "other"


def test_get_rca_triggers_filters_corrections_and_failures():
    classified = [
        {"turn_index": 0, "label": "new_task", "text": "hello"},
        {"turn_index": 1, "label": "correction", "text": "wrong"},
        {"turn_index": 2, "label": "failure_report", "text": "error"},
        {"turn_index": 3, "label": "acceptance", "text": "good"},
    ]
    triggers = get_rca_triggers(classified)
    assert len(triggers) == 2
    assert triggers[0]["label"] == "correction"
    assert triggers[1]["label"] == "failure_report"


def test_get_session_skeleton():
    classified = [
        {"turn_index": 0, "label": "new_task", "text": "hello"},
        {"turn_index": 1, "label": "correction", "text": "wrong"},
        {"turn_index": 2, "label": "failure_report", "text": "error"},
        {"turn_index": 3, "label": "acceptance", "text": "good"},
        {"turn_index": 4, "label": "continuation", "text": "ok"},
    ]
    skeleton = get_session_skeleton(classified)
    assert skeleton["total_user_messages"] == 5
    assert skeleton["task_count"] == 1
    assert skeleton["correction_count"] == 1
    assert skeleton["failure_report_count"] == 1
    assert skeleton["acceptance_count"] == 1
    assert skeleton["correction_rate"] == 0.2


def test_classification_schema_is_json_object():
    schema = CLASSIFICATION_SCHEMA
    assert schema["type"] == "json_object"
