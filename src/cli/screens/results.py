# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Findings display screen — rich markdown-style output."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static


class ResultsScreen(Screen):
    """Markdown-style findings report."""

    BINDINGS = [("q", "quit_app", "Quit"), ("s", "save", "Save")]

    def __init__(self, findings: list[dict], session_count: int):
        super().__init__()
        self.findings = findings
        self.session_count = session_count

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"[bold]Findings[/] — {len(self.findings)} recurring across {self.session_count} sessions", id="results-title")
        yield Static("", id="results-body")
        yield Footer()

    def on_mount(self) -> None:
        body = self.query_one("#results-body", Static)
        if not self.findings:
            body.update(
                f"[green]All clean[/] — no recurring issues across {self.session_count} sessions"
            )
            return

        lines = ["", f"[dim]{'='*50}[/]", ""]
        for i, f in enumerate(self.findings):
            sev = f.get("severity", 1)
            sev_color = {5: "red", 4: "red", 3: "yellow"}.get(sev, "dim")
            sev_bar = "#" * sev + "-" * (5 - sev)
            category = f.get("category", "unknown")
            rule = f.get("agents_md_rule", "")
            sessions = f.get("session_id", "")
            convention = f.get("is_convention", False)
            dont = f.get("dont_do", "")
            do = f.get("do_instead", "")

            lines.append(f"## Finding {i+1}")
            lines.append(f" Severity   : [{sev_color}]{sev_bar}[/] {sev}/5")
            lines.append(f" Category   : [bold]{category}[/]")
            if rule:
                lines.append(f" Rule       : {rule}")
            lines.append(f" Session    : [dim]{sessions}[/]")
            if convention and dont:
                lines.append(f" Don't      : [red]{dont}[/]")
            if convention and do:
                lines.append(f" Do instead : [green]{do}[/]")
            lines.append("")

        lines.append(f"[dim]{'='*50}[/]")
        body.update("\n".join(lines))

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_save(self) -> None:
        import json
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"blackbox-findings-{timestamp}.json"
        with open(filename, "w") as f:
            json.dump(self.findings, f, indent=2)
        self.notify(f"Saved to {filename}")
