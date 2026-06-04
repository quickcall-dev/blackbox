# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Blocking analysis progress screen with live phase output."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Label, Static

STAGE_NAMES = [
    "P0 Normalize", "P1 Classify", "P2 Context", "P3 Root-Cause",
    "P4a Behavior", "P4b Cluster", "P4c Convention",
    "P5 Aggregate", "P6 Scope",
]
STAGE_KEYS = [
    "p0_normalize", "p1_classify", "p2_context", "p3_rca",
    "p4a_behavior", "p4b_cluster", "p4c_convention",
    "p5_aggregate", "p6_scope",
]


class ProgressScreen(Screen):
    """Shows analysis pipeline progress with live phase output in right pane."""

    DEFAULT_CSS = """
    ProgressScreen {
        padding: 0;
    }
    ProgressScreen > Horizontal {
        height: 1fr;
    }
    #stage-panel {
        width: 32;
        padding: 1 2;
        border-right: solid $primary;
    }
    #output-panel {
        width: 1fr;
        padding: 1 2;
    }
    #output-scroll {
        height: 100%;
    }
    .stage-done {
        color: $success;
    }
    .stage-current {
        color: $warning;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("q", "quit_app", "Quit"),
        Binding("up", "cursor_up", "Up", priority=True),
        Binding("down", "cursor_down", "Down", priority=True),
        Binding("pageup", "scroll_page_up", "PgUp"),
        Binding("pagedown", "scroll_page_down", "PgDn"),
        Binding("ctrl+p", "command_palette", "Palette"),
    ]

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id
        self._completed: set[int] = set()
        self._current: int = 0
        self._stage_labels: dict[int, Static] = {}
        self._started_at: float = 0
        self._output_content: Static | None = None
        self._output_scroll: ScrollableContainer | None = None
        self._stage_outputs: dict[int, str] = {}
        self._selected_index: int = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="stage-panel"):
                yield Label("Analyzing sessions", id="progress-title")
                yield Label(f"[dim]{self.run_id}[/]", id="progress-run-id")
                yield Label("Elapsed: 0s", id="progress-elapsed")
                yield Label("", id="progress-spacer")
                for i, name in enumerate(STAGE_NAMES):
                    label = Static(f" [ ] {name}", id=f"stage-{i}")
                    self._stage_labels[i] = label
                    yield label
                yield Label("", id="progress-spacer2")
                yield Label("[dim]↑↓ Navigate[/]", id="nav-hint")
            with Vertical(id="output-panel"):
                with ScrollableContainer(id="output-scroll"):
                    yield Static("[dim]Waiting for first phase to complete...[/]", id="output-content")
        yield Footer()

    def on_mount(self) -> None:
        import time
        self._started_at = time.time()
        self._output_content = self.query_one("#output-content", Static)
        self._output_scroll = self.query_one("#output-scroll", ScrollableContainer)
        self._timer = self.set_interval(1, self._tick_elapsed)

    def _tick_elapsed(self) -> None:
        import time
        elapsed = int(time.time() - self._started_at)
        minutes = elapsed // 60
        seconds = elapsed % 60
        if minutes > 0:
            text = f"Elapsed: {minutes}m {seconds}s"
        else:
            text = f"Elapsed: {seconds}s"
        label = self.query_one("#progress-elapsed", Static)
        label.update(f"[dim]{text}[/]")

    def update_progress(self, completed_count: int) -> None:
        """Mark stages 0..completed_count-1 as done, stage completed_count as current."""
        for i in range(completed_count):
            if i not in self._completed:
                self._completed.add(i)
        self._current = completed_count
        # Auto-follow: snap cursor to the latest completed stage so user sees fresh output
        if completed_count > 0:
            self._selected_index = completed_count - 1
        self._refresh_stage_list()
        self._show_selected_output()
        # Stop timer when all stages done
        if completed_count >= len(STAGE_NAMES) and self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _refresh_stage_list(self) -> None:
        for i, label in self._stage_labels.items():
            prefix = " [green]✓[/]" if i in self._completed else " [ ]"
            if i == self._current and i not in self._completed:
                prefix = " [bold yellow]*[/]"
            cursor = "[bold cyan]>[/]" if i == self._selected_index else " "
            if i == self._selected_index:
                label.update(f"{cursor}{prefix} [bold]{STAGE_NAMES[i]}[/]")
            else:
                label.update(f"{cursor}{prefix} [dim]{STAGE_NAMES[i]}[/]")

    def show_phase_output(self, stage_key: str, stage_data: dict) -> None:
        """Save and optionally display a completed stage's output."""
        idx = STAGE_KEYS.index(stage_key)
        text = self._render_stage(stage_key, stage_data)
        self._stage_outputs[idx] = text
        if idx == self._selected_index and self._output_content is not None:
            self._output_content.update(text)

    def action_cursor_up(self) -> None:
        if self._selected_index > 0:
            self._selected_index -= 1
            self._refresh_stage_list()
            self._show_selected_output()

    def action_cursor_down(self) -> None:
        if self._selected_index < len(STAGE_NAMES) - 1:
            self._selected_index += 1
            self._refresh_stage_list()
            self._show_selected_output()

    def action_scroll_page_up(self) -> None:
        if self._output_scroll is not None:
            self._output_scroll.scroll_up(animate=False)

    def action_scroll_page_down(self) -> None:
        if self._output_scroll is not None:
            self._output_scroll.scroll_down(animate=False)

    def _show_selected_output(self) -> None:
        if self._output_content is None:
            return
        if self._selected_index in self._stage_outputs:
            self._output_content.update(self._stage_outputs[self._selected_index])
        elif self._selected_index == self._current and self._current not in self._completed:
            self._output_content.update("[dim]Stage running...[/]")
        else:
            self._output_content.update("[dim]Stage not yet started.[/]")

    def show_error(self, message: str) -> None:
        label = self._stage_labels.get(self._current)
        if label:
            label.update(f" [red]! {STAGE_NAMES[self._current]} - {message}[/]")
        err_text = f"[red bold]Error:[/] {message}"
        self._stage_outputs[self._current] = err_text
        if self._output_content and self._selected_index == self._current:
            self._output_content.update(err_text)

    def action_quit_app(self) -> None:
        self.app.exit()

    def _render_stage(self, key: str, data: dict) -> str:
        """Format stage data into rich display text."""
        lines: list[str] = []
        lines.append(f"[bold underline]{key}[/]")
        lines.append("")

        if key == "p0_normalize":
            sessions = data.get("sessions", {})
            lines.append(f"Sessions normalized: [bold]{len(sessions)}[/]")
            for sid, sdata in sessions.items():
                source = sdata.get("source", "unknown")
                msgs = sdata.get("message_count", 0)
                lines.append(f"  • {sid} [{source}] {msgs} msgs")

        elif key == "p1_classify":
            sessions = data.get("sessions", [])
            trigger_count = data.get("trigger_count", 0)
            lines.append(f"Sessions: [bold]{len(sessions)}[/]")
            lines.append(f"Total triggers: [bold yellow]{trigger_count}[/]")
            for s in sessions:
                sid = s.get("session_id", "")
                tcount = len(s.get("triggers", []))
                lines.append(f"  • {sid} — [bold]{tcount}[/] triggers")

        elif key == "p2_context":
            windows = data.get("windows", [])
            lines.append(f"Context windows built: [bold]{len(windows)}[/]")
            for w in windows:
                sid = w.get("session_id", "")
                tidx = w.get("trigger", {}).get("turn_index", "?")
                ctx_len = len(w.get("context", []))
                lines.append(f"  • {sid} turn {tidx} — {ctx_len} context turns")

        elif key == "p3_rca":
            findings = data.get("findings", [])
            fp = data.get("false_positive_count", 0)
            lines.append(f"Findings: [bold green]{len(findings)}[/]")
            if fp:
                lines.append(f"False positives filtered: [dim]{fp}[/]")
            for f in findings:
                cat = f.get("category", "unknown")
                sev = f.get("severity", 1)
                rule = f.get("agents_md_rule", "")
                lines.append(f"  • [bold]{cat}[/] sev={sev} — {rule}")

        elif key == "p4a_behavior":
            findings = data.get("findings", [])
            lines.append(f"Findings classified: [bold]{len(findings)}[/]")
            types: dict[str, int] = {}
            for f in findings:
                rt = f.get("rule_type", "unknown")
                types[rt] = types.get(rt, 0) + 1
            for rt, count in sorted(types.items(), key=lambda x: -x[1]):
                lines.append(f"  • {rt}: [bold]{count}[/]")

        elif key == "p4b_cluster":
            patterns = data.get("patterns", [])
            one_offs = data.get("one_off_indices", [])
            lines.append(f"Patterns found: [bold]{len(patterns)}[/]")
            lines.append(f"One-off findings: [dim]{len(one_offs)}[/]")
            for p in patterns:
                label = p.get("label", "unknown")
                idx_count = len(p.get("finding_indices", []))
                lines.append(f"  • {label} ([bold]{idx_count}[/] findings)")

        elif key == "p4c_convention":
            conventions = data.get("conventions", [])
            lines.append(f"Conventions detected: [bold]{len(conventions)}[/]")
            for c in conventions:
                ctype = c.get("convention_type", "unknown")
                dont = c.get("dont_do", "")
                do = c.get("do_instead", "")
                lines.append(f"  • [bold]{ctype}[/]")
                if dont:
                    lines.append(f"    Don't: {dont}")
                if do:
                    lines.append(f"    Do: {do}")

        elif key == "p5_aggregate":
            total = data.get("total_findings", 0)
            recurring = data.get("recurring_findings", 0)
            cat_dist = data.get("category_distribution", {})
            sev_dist = data.get("severity_distribution", {})
            lines.append(f"Total findings: [bold]{total}[/]")
            lines.append(f"Recurring: [bold green]{recurring}[/]")
            if cat_dist:
                lines.append("Categories:")
                for cat, count in sorted(cat_dist.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {cat}: [bold]{count}[/]")
            if sev_dist:
                lines.append("Severity:")
                for sev, count in sorted(sev_dist.items(), key=lambda x: int(x[0])):
                    bar = "█" * count + "░" * (total - count)
                    lines.append(f"  • sev {sev}: [bold]{count}[/] {bar}")
            findings = data.get("findings", [])
            for f in findings:
                cat = f.get("category", "?")
                sev = f.get("severity", 1)
                rule = f.get("agents_md_rule", "")
                lines.append(f"  • [{cat}] sev={sev} — {rule}")

        elif key == "p6_scope":
            lines.append("[yellow]Directories checked[/]")
            lines.append("")
            lines.append("[dim]Note: Repository and developer attribution requires additional configuration (e.g. git metadata, user profiles) which is currently out of scope. Findings are grouped by inferred directory names only.[/]")
            lines.append("")
            repos = data.get("repos", {})
            dev_repo = data.get("dev_repo", {})
            lines.append(f"Directories: [bold]{len(repos)}[/]")
            for repo, findings in repos.items():
                lines.append(f"  • {repo}: [bold]{len(findings)}[/] findings")
            if dev_repo:
                lines.append(f"Developer-directory pairs: [bold]{len(dev_repo)}[/]")
                for pair, findings in dev_repo.items():
                    lines.append(f"  • {pair}: [bold]{len(findings)}[/] findings")

        else:
            lines.append(str(data))

        return "\n".join(lines)
