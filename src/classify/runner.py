# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Helpers for building and parsing message classifications."""

from collections import Counter


def build_classification_prompt(
    user_messages: list[dict],
    max_chars_per_msg: int = 500,
) -> str:
    """Build the user-facing classification prompt."""
    lines = []
    for message in user_messages:
        text = message["text"][:max_chars_per_msg]
        if len(message["text"]) > max_chars_per_msg:
            text += "..."
        lines.append(f'[Turn {message["turn_index"]}] {text}')

    return (
        "Classify each user message below. Return a JSON array with one "
        "{turn, label} object per message, in the same order.\n\n"
        + "\n\n".join(lines)
    )


def parse_classifications(response: list[dict] | dict, user_messages: list[dict]) -> list[dict]:
    if isinstance(response, dict):
        response = response.get("classifications", [])
    """Merge model output back into the original user messages."""
    by_turn = {message["turn_index"]: message for message in user_messages}

    classified = []
    for item in response:
        turn = item.get("turn")
        if turn not in by_turn:
            continue
        classified.append({**by_turn[turn], "label": item.get("label", "other")})

    classified_turns = {message["turn_index"] for message in classified}
    for message in user_messages:
        if message["turn_index"] not in classified_turns:
            classified.append({**message, "label": "other"})

    classified.sort(key=lambda message: message["turn_index"])
    return classified


def get_rca_triggers(classified_messages: list[dict]) -> list[dict]:
    """Return messages that should trigger RCA."""
    return [
        message
        for message in classified_messages
        if message["label"] in ("correction", "failure_report")
    ]


def get_session_skeleton(classified_messages: list[dict]) -> dict:
    """Return aggregate counts and rates for classified messages."""
    counts = Counter(message["label"] for message in classified_messages)
    total = len(classified_messages)
    return {
        "total_user_messages": total,
        "label_counts": dict(counts),
        "task_count": counts.get("new_task", 0),
        "correction_count": counts.get("correction", 0),
        "failure_report_count": counts.get("failure_report", 0),
        "acceptance_count": counts.get("acceptance", 0),
        "abandonment_count": counts.get("abandonment", 0),
        "correction_rate": counts.get("correction", 0) / max(1, total),
    }
