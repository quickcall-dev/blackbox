# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Color-coded severity indicator."""

from textual.widgets import Label


class SeverityBar(Label):
    """Bar showing severity level with color."""

    COLORS = {5: "red", 4: "red", 3: "yellow", 2: "dim", 1: "dim"}

    def __init__(self, severity: int):
        color = self.COLORS.get(severity, "dim")
        bar = "#" * severity + "-" * (5 - severity)
        super().__init__(f"[{color}][{bar}] {severity}/5[/]")
