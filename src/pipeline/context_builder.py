# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Context window helpers for standalone trace analysis."""


def build_context_window(
    annotated: dict,
    trigger_turn: int,
    before: int = 15,
    after: int = 5,
    max_content_per_msg: int = 2000,
) -> list[dict]:
    """Build a dense context window around a trigger turn."""
    messages = annotated.get("messages", [])
    start = max(0, trigger_turn - before)
    end = min(len(messages), trigger_turn + after + 1)

    context = []
    prev_content = None

    for turn in range(start, end):
        msg = messages[turn]
        content = (msg.get("real_content") or "").strip()
        if not content:
            continue
        if content == prev_content:
            continue
        prev_content = content

        if max_content_per_msg > 0 and len(content) > max_content_per_msg:
            content = content[:max_content_per_msg]

        context.append({
            "original_turn": turn,
            "role": msg.get("role", "other"),
            "content": content,
            "content_len": len(content),
        })

    return context


def format_context_for_prompt(
    context: list[dict],
    max_content_per_msg: int = 500,
) -> str:
    """Format context for prompt inclusion."""
    lines = []
    for msg in context:
        content = msg["content"]
        if max_content_per_msg > 0 and len(content) > max_content_per_msg:
            content = content[:max_content_per_msg]
        lines.append(f"[Turn {msg['original_turn']}] [{msg['role']}] {content}")
    return "\n\n".join(lines)


def context_stats(context: list[dict]) -> dict:
    """Summarize context contents."""
    by_role = {}
    total_chars = 0

    for msg in context:
        role = msg.get("role", "other")
        by_role[role] = by_role.get(role, 0) + 1
        total_chars += msg.get("content_len", len(msg.get("content", "")))

    if context:
        turn_range = [context[0]["original_turn"], context[-1]["original_turn"]]
    else:
        turn_range = []

    return {
        "total": len(context),
        "by_role": by_role,
        "total_chars": total_chars,
        "turn_range": turn_range,
    }


def extract_user_messages(annotated: dict) -> list[dict]:
    """Extract non-empty user messages with their message indices."""
    user_messages = []
    for i, msg in enumerate(annotated.get("messages", [])):
        if msg.get("role") != "real_user":
            continue
        text = (msg.get("real_content") or "").strip()
        if not text:
            continue
        user_messages.append({
            "turn_index": i,
            "turn_number": msg.get("turn_number"),
            "text": text,
        })
    return user_messages
