# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Scan filesystem for AI coding session traces."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import os


@dataclass
class SessionInfo:
    """Discovered session metadata."""

    path: Path
    session_id: str
    source: str
    last_modified: float
    project: str = ""
    user_messages: list[str] = field(default_factory=list)
    message_count: int = 0


def scan_sessions(base_dir: Path, source: str) -> list[SessionInfo]:
    """Scan a base directory for session files.

    Args:
        base_dir: Root directory to scan (e.g. ~/.claude).
        source: Source type key ('claude_code', 'codex_cli', 'pi').

    Returns:
        List of SessionInfo sorted by last_modified descending.
    """
    sessions: list[SessionInfo] = []

    for jsonl_file in base_dir.rglob("*.jsonl"):
        try:
            info = _parse_session_file(jsonl_file, source)
            if info is not None:
                sessions.append(info)
        except Exception:
            continue

    sessions.sort(key=lambda s: s.last_modified, reverse=True)
    return sessions


SOURCE_PATHS = {
    "claude_code": Path.home() / ".claude" / "projects",
    "codex_cli": Path.home() / ".codex" / "sessions",
    "pi": Path.home() / ".pi" / "agent" / "sessions",
}


def discover_all() -> list[SessionInfo]:
    """Scan all known source directories for sessions."""
    all_sessions: list[SessionInfo] = []
    for source, base_dir in SOURCE_PATHS.items():
        if base_dir.exists():
            all_sessions.extend(scan_sessions(base_dir, source))
    all_sessions.sort(key=lambda s: s.last_modified, reverse=True)
    return all_sessions


def _parse_session_file(path: Path, source: str) -> SessionInfo | None:
    """Parse a single session file and extract metadata."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    try:
        text = path.read_text()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None
    except Exception:
        return None

    session_id = ""
    user_messages: list[str] = []
    for line_str in lines:
        try:
            obj = json.loads(line_str)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        if not session_id:
            session_id = obj.get("sessionId") or obj.get("session_id") or obj.get("id") or ""
            if not session_id and source == "pi" and obj.get("type") == "session":
                session_id = obj.get("id", "")

        if source in ("claude_code", "codex_cli"):
            if obj.get("type") == "user":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    user_messages.append(content.strip())
        elif source == "pi":
            if obj.get("type") == "message":
                msg = obj.get("message", {})
                if msg.get("role") == "user":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        texts = [
                            p.get("text", "") for p in content
                            if isinstance(p, dict) and p.get("type") == "text"
                        ]
                        if texts:
                            user_messages.append("\n".join(texts))
                    elif isinstance(content, str) and content.strip():
                        user_messages.append(content.strip())

    if not session_id:
        return None

    return SessionInfo(
        path=path,
        session_id=str(session_id),
        source=source,
        last_modified=mtime,
        project=_extract_project(path, source),
        user_messages=user_messages,
        message_count=len(user_messages),
    )


def _extract_project(path: Path, source: str) -> str:
    """Extract project directory name from session file path."""
    if source == "claude_code":
        # ~/.claude/projects/<project>/<session>.jsonl
        return path.parent.name
    elif source == "codex_cli":
        # ~/.codex/sessions/<project>/.../<session>.jsonl
        parts = path.parts
        for i, p in enumerate(parts):
            if p == "sessions" and i + 1 < len(parts):
                return parts[i + 1]
        return ""
    elif source == "pi":
        # ~/.pi/agent/sessions/<project>/<session>.jsonl
        return path.parent.name
    return ""
