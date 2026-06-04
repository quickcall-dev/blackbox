# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Deduplication helpers for annotated message streams."""


def dedup_annotated_messages(annotated: dict) -> dict:
    """Remove consecutive duplicate real_user messages."""
    messages = annotated["messages"]
    deduped = []
    prev_content = None
    prev_role = None
    removed = 0

    for msg in messages:
        if (
            msg["role"] == "real_user"
            and prev_role == "real_user"
            and msg["real_content"] == prev_content
            and prev_content is not None
        ):
            removed += 1
            continue
        deduped.append(msg)
        prev_content = msg.get("real_content")
        prev_role = msg["role"]

    result = dict(annotated)
    result["messages"] = deduped
    result["stats"] = dict(annotated.get("stats", {}))
    result["stats"]["duplicates_removed"] = removed
    return result
