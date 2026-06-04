# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Browser screen — split view with session list and detail panel."""

import asyncio
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from src.cli.discovery import SessionInfo


def _format_time(ts: float) -> str:
    """Format a Unix timestamp for display."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class BrowserScreen(Screen):
    """Session browser with split layout: session list | detail panel.

    Shows discovered sessions in a DataTable. Selecting a row shows
    details in the right panel. Active sources can be toggled via keys.
    """

    BINDINGS = [
        ("space", "toggle_selection", "Select"),
        ("ctrl+a", "submit_analysis", "Analyze"),
        ("1", "toggle_claude", "Claude"),
        ("2", "toggle_codex", "Codex"),
        ("3", "toggle_pi", "Pi"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, sessions: list[SessionInfo]) -> None:
        super().__init__()
        self.all_sessions = sessions
        # Cap visible sessions for performance
        self.sessions = sessions[:200]
        self.selected: set[int] = set()
        self.active_sources: set[str] = {"claude_code", "codex_cli", "pi"}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="session-list")
            with Vertical(id="detail-panel"):
                yield Static("", id="detail-title")
                yield Static("", id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the session table on mount."""
        table = self.query_one("#session-list", DataTable)
        table.cursor_type = "row"
        table.add_columns("", "Source", "Project", "Session", "Time", "Msgs")

        source_labels = {"claude_code": "claude", "codex_cli": "codex", "pi": "pi"}

        for i, s in enumerate(self.sessions):
            if s.source not in self.active_sources:
                continue
            sid = s.session_id[-12:] if len(s.session_id) > 12 else s.session_id
            label = source_labels.get(s.source, s.source)
            mark = "[bold yellow]*[/]" if i in self.selected else " "
            table.add_row(mark, label, s.project[-24:] if len(s.project) > 24 else s.project, sid, _format_time(s.last_modified), str(s.message_count), key=str(i))

        self.query_one("#detail-body", Static).update(
            "[dim]space[/] select  [dim]ctrl+a[/] analyze  [dim]1/2/3[/] filter  [dim]q[/] quit"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail panel when a row is highlighted."""
        if event.row_key is None or not event.row_key.value:
            return

        try:
            idx = int(event.row_key.value)
        except (ValueError, TypeError):
            return

        if idx >= len(self.sessions):
            return

        s = self.sessions[idx]
        detail_title = self.query_one("#detail-title", Static)
        detail_body = self.query_one("#detail-body", Static)

        detail_title.update(f"[bold]{s.source}[/]  [dim]{s.project}[/]  {s.session_id}")

        lines = [f"[dim]{_format_time(s.last_modified)}[/]", ""]
        for j, msg in enumerate(s.user_messages[:10]):
            lines.append(f"[bold]#{j + 1}[/] {msg[:120]}")
        detail_body.update("\n".join(lines))

    def action_toggle_selection(self) -> None:
        """Toggle the currently highlighted row as selected."""
        table = self.query_one("#session-list", DataTable)
        if table.cursor_row is None:
            return
        idx = self._visible_index(table.cursor_row)
        if idx is None:
            return
        if idx in self.selected:
            self.selected.discard(idx)
        else:
            self.selected.add(idx)
        # Update just the marker cell, don't rebuild
        mark = "[bold yellow]*[/]" if idx in self.selected else " "
        row_key = table.ordered_rows[table.cursor_row].key
        col_key = list(table.columns.keys())[0]
        table.update_cell(row_key, col_key, mark)

    def _visible_index(self, visible_row: int) -> int | None:
        """Map a visible table row to the original session list index."""
        visible = [i for i, s in enumerate(self.sessions) if s.source in self.active_sources]
        if visible_row < len(visible):
            return visible[visible_row]
        return None

    def _toggle_source(self, source: str) -> None:
        if source in self.active_sources:
            self.active_sources.discard(source)
        else:
            self.active_sources.add(source)
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Clear and rebuild the session table with current filters."""
        table = self.query_one("#session-list", DataTable)
        table.clear()
        source_labels = {"claude_code": "claude", "codex_cli": "codex", "pi": "pi"}
        for i, s in enumerate(self.sessions):
            if s.source not in self.active_sources:
                continue
            sid = s.session_id[-12:] if len(s.session_id) > 12 else s.session_id
            label = source_labels.get(s.source, s.source)
            mark = "[bold yellow]*[/]" if i in self.selected else " "
            table.add_row(mark, label, s.project[-24:] if len(s.project) > 24 else s.project, sid, _format_time(s.last_modified), str(s.message_count), key=str(i))

    async def action_submit_analysis(self) -> None:
        """Gather selected session files and submit to API."""
        if not self.selected:
            self.notify("No sessions selected", severity="warning")
            return

        from src.cli.client import BlackboxClient
        from src.cli.config import get_api_url
        from src.cli.screens.api_config import ApiConfigScreen

        api_url = get_api_url()
        client = BlackboxClient(base_url=api_url)

        # Retry health check once — server may still be warming up
        ok = await client.health()
        if not ok:
            await asyncio.sleep(1)
            ok = await client.health()
        if not ok:
            # Push config screen with callback — can't use push_screen_wait outside worker
            config_screen = ApiConfigScreen(default_url=api_url)
            self.app.push_screen(config_screen, self._on_config_done)
            return

        await self._run_analysis(client)

    def _on_config_done(self, new_url: str | None) -> None:
        """Callback after user enters URL in ApiConfigScreen."""
        if not new_url:
            return
        # Re-run the health check + analysis with the new URL
        self.run_worker(self._retry_analysis(new_url), exclusive=True)

    async def _retry_analysis(self, new_url: str) -> None:
        """Health check with new URL, then run analysis if reachable."""
        from src.cli.client import BlackboxClient
        client = BlackboxClient(base_url=new_url)
        ok = await client.health()
        if not ok:
            self.notify(f"Still unreachable at {new_url}", severity="error")
            return
        await self._run_analysis(client)

    async def _run_analysis(self, client) -> None:
        """Submit files and poll for completion."""
        from src.cli.screens.progress import ProgressScreen, STAGE_KEYS

        # Gather selected files
        selected_files: list[Path] = []
        for idx in sorted(self.selected):
            if idx < len(self.sessions):
                selected_files.append(self.sessions[idx].path)

        # Submit
        try:
            run_id = await client.analyze(selected_files)
        except Exception as e:
            self.notify(f"Upload failed: {e}", severity="error")
            return

        # Show progress screen
        progress = ProgressScreen(run_id)
        await self.app.push_screen(progress)

        # Poll for completion
        completed_stages = 0
        while True:
            try:
                run = await client.get_run(run_id)
            except Exception:
                await asyncio.sleep(2)
                continue

            status = run.get("status", "running")
            stages = run.get("stages", {})

            # Detect newly completed stages and render their output
            for i, key in enumerate(STAGE_KEYS):
                stage = stages.get(key)
                if isinstance(stage, dict) and stage.get("status") == "done" and i >= completed_stages:
                    progress.update_progress(i + 1)
                    # API flattens stage.data into the summary; reconstruct data dict
                    stage_data = {k: v for k, v in stage.items() if k not in ("status", "started_at", "completed_at", "error")}
                    progress.show_phase_output(key, stage_data)

            done_count = sum(
                1 for s in stages.values()
                if isinstance(s, dict) and s.get("status") == "done"
            )
            if done_count > completed_stages:
                completed_stages = done_count

            if status == "done":
                progress.update_progress(len(STAGE_KEYS))
                # Snap cursor to aggregate stage — that's the summary the user cares about
                progress._selected_index = 7  # p5_aggregate
                progress._refresh_stage_list()
                progress._show_selected_output()
                break
            elif status == "error":
                error = run.get("error", "Unknown error")
                progress.show_error(error)
                return

            await asyncio.sleep(2)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_toggle_claude(self) -> None:
        self._toggle_source("claude_code")

    def action_toggle_codex(self) -> None:
        self._toggle_source("codex_cli")

    def action_toggle_pi(self) -> None:
        self._toggle_source("pi")
