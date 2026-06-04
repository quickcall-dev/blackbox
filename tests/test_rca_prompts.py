# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for RCA prompts and schemas."""

import pytest

from src.rca.prompts import RCA_SCHEMA, RCA_SYSTEM_PROMPT, RCA_USER_TEMPLATE


def test_rca_schema_is_json_object():
    schema = RCA_SCHEMA
    assert schema["type"] == "json_object"


def test_rca_schema_categories_in_prompt():
    assert "wrong_target" in RCA_SYSTEM_PROMPT
    assert "wrong_approach" in RCA_SYSTEM_PROMPT
    assert "domain_logic_error" in RCA_SYSTEM_PROMPT
    assert "incomplete_fix" in RCA_SYSTEM_PROMPT
    assert "communication_miss" in RCA_SYSTEM_PROMPT
    assert "scope_creep" in RCA_SYSTEM_PROMPT


def test_rca_schema_severity_in_prompt():
    assert "severity" in RCA_SYSTEM_PROMPT
    assert "1 = Cosmetic" in RCA_SYSTEM_PROMPT
    assert "5 = Production" in RCA_SYSTEM_PROMPT


def test_rca_schema_specificity_in_prompt():
    assert "specific" in RCA_SYSTEM_PROMPT


def test_rca_user_template_renders_correctly():
    prompt = RCA_USER_TEMPLATE.format(
        correction_turn=5,
        correction_text="fix this bug",
        repo_name="test/repo",
        start=0,
        end=10,
        formatted_context="[Turn 0] [real_user] hello\n[Turn 1] [assistant] hi",
    )
    assert "fix this bug" in prompt
    assert "test/repo" in prompt
    assert "[Turn 0]" in prompt
    assert "## Developer Correction at Turn 5" in prompt
    assert "## Repository: test/repo" in prompt
    assert "## Context Window (Turns 0-10)" in prompt


def test_rca_system_prompt_contains_rules():
    assert "root cause analyst" in RCA_SYSTEM_PROMPT.lower()
    assert "agents_md_rule" in RCA_SYSTEM_PROMPT
    assert "severity" in RCA_SYSTEM_PROMPT
    assert "category" in RCA_SYSTEM_PROMPT
