# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Source badge widget — colored label for session source."""

from textual.widgets import Label

COLORS: dict[str, str] = {
    "claude_code": "magenta",
    "codex_cli": "green",
    "pi": "blue",
}

SHORT_NAMES: dict[str, str] = {
    "claude_code": "claude",
    "codex_cli": "codex",
    "pi": "pi",
}


class SourceBadge(Label):
    """Colored label showing session source (claude/codex/pi)."""

    def __init__(self, source: str) -> None:
        color = COLORS.get(source, "white")
        name = SHORT_NAMES.get(source, source)
        super().__init__(f"[{color}]{name}[/]")
