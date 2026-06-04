# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for session discovery."""

import json
import os
import tempfile
from pathlib import Path
from src.cli.discovery import scan_sessions, SessionInfo


def test_scan_finds_claude_session():
    with tempfile.TemporaryDirectory() as tmp:
        projects_dir = Path(tmp) / "projects" / "test-project"
        projects_dir.mkdir(parents=True)
        session_file = projects_dir / "session-1.jsonl"
        session_file.write_text(
            json.dumps({"type": "user", "uuid": "u1", "sessionId": "s1",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "message": {"content": "hello world"}}) + "\n"
        )
        os.utime(session_file, (1000000, 1000000))

        sessions = scan_sessions(base_dir=Path(tmp), source="claude_code")

        assert len(sessions) == 1
        s = sessions[0]
        assert isinstance(s, SessionInfo)
        assert s.session_id == "s1"
        assert s.source == "claude_code"
        assert len(s.user_messages) == 1
        assert s.user_messages[0] == "hello world"


def test_scan_finds_pi_session():
    with tempfile.TemporaryDirectory() as tmp:
        sessions_dir = Path(tmp) / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "session-pi.jsonl"
        session_file.write_text(
            json.dumps({"type": "session", "id": "pi-1", "timestamp": "2026-01-01T00:00:00Z"}) + "\n" +
            json.dumps({"type": "message", "id": "m1", "timestamp": "2026-01-01T00:01:00Z",
                        "message": {"role": "user", "content": [{"type": "text", "text": "fix this"}]}}) + "\n"
        )
        os.utime(session_file, (2000000, 2000000))

        sessions = scan_sessions(base_dir=Path(tmp), source="pi")

        assert len(sessions) == 1
        assert sessions[0].session_id == "pi-1"
        assert sessions[0].source == "pi"
        assert sessions[0].user_messages == ["fix this"]


from src.cli.discovery import discover_all
from unittest.mock import patch


def test_discover_all_aggregates_sources():
    with patch("src.cli.discovery.scan_sessions") as mock_scan:
        from src.cli.discovery import SessionInfo
        from pathlib import Path

        def fake_scan(base_dir, source):
            return [SessionInfo(
                path=Path(f"/tmp/{source}.jsonl"),
                session_id=f"{source}-1",
                source=source,
                last_modified=1000.0,
                user_messages=["test"],
            )]

        mock_scan.side_effect = fake_scan
        sessions = discover_all()

        sources = {s.source for s in sessions}
        assert "claude_code" in sources
        assert "codex_cli" in sources
        assert "pi" in sources


def test_scan_sorted_by_mtime_descending():
    with tempfile.TemporaryDirectory() as tmp:
        projects_dir = Path(tmp) / "projects" / "p1"
        projects_dir.mkdir(parents=True)
        older = projects_dir / "older.jsonl"
        older.write_text(
            json.dumps({"type": "user", "uuid": "a", "sessionId": "old",
                        "timestamp": "", "message": {"content": "old"}}) + "\n"
        )
        newer = projects_dir / "newer.jsonl"
        newer.write_text(
            json.dumps({"type": "user", "uuid": "b", "sessionId": "new",
                        "timestamp": "", "message": {"content": "new"}}) + "\n"
        )
        os.utime(older, (1000000, 1000000))
        os.utime(newer, (2000000, 2000000))

        sessions = scan_sessions(base_dir=Path(tmp), source="claude_code")

        assert len(sessions) == 2
        assert sessions[0].session_id == "new"
        assert sessions[1].session_id == "old"
