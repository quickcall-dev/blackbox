# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Textual App entry point for Blackbox CLI."""

import sys
from pathlib import Path

import httpx
from textual.app import App

from src.cli.config import get_api_url
from src.cli.discovery import discover_all
from src.config import settings
from src.cli.screens.browser import BrowserScreen
from src.cli.screens.splash import SplashScreen


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


def _health_check() -> dict:
    """Synchronous health check before launching TUI.

    Returns {"ok": True} or {"ok": False, "reason": str, "detail": str}.
    """
    url = get_api_url()
    try:
        resp = httpx.get(f"{url}/health", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                return {"ok": True}
            if data.get("status") == "error" and data.get("reason") == "invalid_api_key":
                return {"ok": False, "reason": "invalid_api_key", "detail": data.get("detail", "")}
            return {"ok": False, "reason": "unhealthy", "detail": str(data)}
    except Exception as exc:
        return {"ok": False, "reason": "unreachable", "detail": str(exc)}


def main():
    """Entry point for `quickcall` CLI."""
    result = _health_check()
    if not result["ok"]:
        api_url = get_api_url()
        if result["reason"] == "invalid_api_key":
            print(f"Error: API key rejected by {settings.model}", file=sys.stderr)
            print("Check OPENAI_API_KEY in your .env file", file=sys.stderr)
        else:
            print(f"Error: Blackbox API unreachable at {api_url}", file=sys.stderr)
            print("Run the server first:  bash dev.sh", file=sys.stderr)
            config_path = Path.home() / ".config" / "quickcall" / "config.json"
            if config_path.exists():
                print(f"Cached URL in {config_path} — delete it or override with BLACKBOX_API_URL", file=sys.stderr)
        sys.exit(1)

    app = BlackboxApp()
    app.run()
