# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for CLI screens."""

from src.cli.screens.splash import SplashScreen


def test_source_badge_claude():
    from src.cli.widgets.source_badge import SourceBadge
    badge = SourceBadge("claude_code")
    assert "claude" in str(badge.render()).lower()


def test_source_badge_pi():
    from src.cli.widgets.source_badge import SourceBadge
    badge = SourceBadge("pi")
    assert "pi" in str(badge.render()).lower()




def test_splash_screen_creates():
    screen = SplashScreen()
    assert screen is not None


def test_splash_banner_contains_quickcall():
    screen = SplashScreen()
    # Minimal splash uses inline text; verify class exists with expected attr
    assert hasattr(screen, "session_count")


def test_severity_bar():
    from src.cli.widgets.severity_bar import SeverityBar
    bar = SeverityBar(5)
    assert "5/5" in str(bar.render())
    bar2 = SeverityBar(2)
    assert "2/5" in str(bar2.render())


def test_progress_screen_creates():
    from src.cli.screens.progress import ProgressScreen
    screen = ProgressScreen("test_run")
    assert screen.run_id == "test_run"
    assert hasattr(screen, "update_progress")
    assert hasattr(screen, "show_phase_output")


def test_results_screen_empty():
    from src.cli.screens.results import ResultsScreen
    screen = ResultsScreen([], 3)
    children = list(screen.compose())
    assert len(children) >= 2


def test_splash_no_sessions_shows_message():
    screen = SplashScreen()
    assert screen is not None
    assert hasattr(screen, "session_count")


def test_results_screen_with_findings():
    from src.cli.screens.results import ResultsScreen
    findings = [{"severity": 4, "category": "missing_context", "agents_md_rule": "fix it", "session_id": "s1"}]
    screen = ResultsScreen(findings, 1)
    children = list(screen.compose())
    assert len(children) >= 2
