# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Prompts and schema for user message classification."""

MESSAGE_TYPES = [
    "new_task",
    "correction",
    "acceptance",
    "failure_report",
    "scope_change",
    "abandonment",
    "continuation",
    "question",
    "other",
]

CLASSIFICATION_SYSTEM_PROMPT = """\
You are classifying user messages in an AI coding session. For each message, assign exactly one label.

Labels:
- new_task: developer starts a new task or gives a new instruction to build/fix/change something
- correction: developer says the AI did something wrong, needs to redo, used wrong approach, wrong file, or didn't follow instructions. Includes "still not working", pasting errors after AI's fix attempt, rejecting AI's output, "that's not what I asked"
- acceptance: developer approves AI's work ("looks good", "perfect", "ship it", "commit")
- failure_report: developer reports an error, pastes a stack trace, shows broken output. The AI hasn't attempted a fix yet — this is the initial report
- scope_change: developer changes direction mid-task, adds/removes requirements, pivots ("actually let's also", "forget that part", "let's try a different approach")
- abandonment: developer gives up on current approach ("never mind", "I'll do it manually", "let's skip this")
- continuation: developer says continue, ok, go ahead, proceed, next ("ok", "do it", "yes", "continue", "next")
- question: developer asks a question without implying AI did something wrong ("how does X work?", "what's the best way to?", "can you explain?")
- other: greetings, thanks, meta-comments, or anything that doesn't fit above

Important:
- "still not working" after AI attempted a fix = correction (not failure_report)
- Pasting a stack trace AFTER AI's fix attempt = correction (showing the fix didn't work)
- Pasting a stack trace as the INITIAL problem = failure_report
- "no" at start of message usually = correction
- "ok" or "yes" alone = continuation
- Brief messages like "do it", "go ahead" = continuation
- "wait" alone = other (thinking pause)

Return JSON in this exact structure:
{"classifications": [{"turn": 0, "label": "new_task"}, ...]}
"""

CLASSIFICATION_SCHEMA = {"type": "json_object"}
