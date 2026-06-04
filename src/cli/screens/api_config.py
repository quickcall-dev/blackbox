# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Screen to configure the Blackbox API URL when unreachable."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from src.cli.config import save_config


class ApiConfigScreen(Screen):
    """Prompt user for API URL when health check fails."""

    DEFAULT_CSS = """
    ApiConfigScreen {
        align: center middle;
    }
    ApiConfigScreen > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
    }
    #title {
        text-align: center;
        text-style: bold;
        color: red;
    }
    #hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    #url-input {
        margin-top: 1;
    }
    #buttons {
        width: 100%;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [("q", "quit_app", "Quit")]

    def __init__(self, default_url: str = "http://localhost:8000") -> None:
        super().__init__()
        self._default = default_url

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("API Unreachable", id="title")
            yield Label(
                "The Blackbox API could not be reached.\n"
                "Make sure the server is running, then enter the URL below.",
                id="hint",
            )
            yield Input(value=self._default, placeholder="http://localhost:8000", id="url-input")
            with Vertical(id="buttons"):
                yield Button("Connect", variant="primary", id="connect-btn")
                yield Button("Quit", variant="error", id="quit-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-btn":
            self.app.exit()
            return

        inp = self.query_one("#url-input", Input)
        url = inp.value.strip()
        if not url:
            self.notify("Please enter a URL", severity="warning")
            return

        # Save for next time
        save_config(api_url=url)

        # Notify the browser screen to retry with the new URL
        self.dismiss(url)

    def action_quit_app(self) -> None:
        self.app.exit()
