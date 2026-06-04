# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Textual App entry point for Blackbox CLI."""

from textual.app import App

from src.cli.discovery import discover_all
from src.cli.screens.splash import SplashScreen
from src.cli.screens.browser import BrowserScreen


class BlackboxApp(App):
    """Main Blackbox TUI application."""

    TITLE = "QuickCall - Blackbox"

    def on_mount(self) -> None:
        splash = SplashScreen()
        self.push_screen(splash)
        self.run_worker(self._discover_and_open(), exclusive=True)

    async def _discover_and_open(self) -> None:
        import asyncio

        # Let splash render first
        await asyncio.sleep(0.1)

        # Discover
        sessions = discover_all()

        # Update splash count
        splash = self.screen
        if isinstance(splash, SplashScreen):
            splash._discovering = False
            splash.session_count = len(sessions)
            splash.refresh()

        await asyncio.sleep(1.5)

        self.push_screen(BrowserScreen(sessions))


def main():
    """Entry point for `quickcall` CLI."""
    app = BlackboxApp()
    app.run()
