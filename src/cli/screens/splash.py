# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Splash screen with minimal centered banner."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, Static


class SplashScreen(Screen):
    """Splash screen shown on app launch. Dismissed by app worker."""

    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
    }
    SplashScreen > Vertical {
        width: auto;
        height: auto;
        align: center middle;
    }
    #splash-line {
        width: auto;
        text-align: center;
        color: cyan;
        text-style: bold;
    }
    #splash-sub {
        width: auto;
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.session_count = 0
        self._discovering = True

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("QuickCall  Blackbox", id="splash-line")
            if self._discovering:
                yield Label("Discovering sessions...", id="splash-sub")
            elif self.session_count == 0:
                yield Label(
                    "No sessions found in ~/.claude, ~/.codex, ~/.pi",
                    id="splash-sub",
                )
            else:
                yield Label(
                    f"{self.session_count} sessions found",
                    id="splash-sub",
                )
