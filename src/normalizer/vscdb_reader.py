# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Reader for Cursor's state.vscdb SQLite databases."""


import base64
import json
import re
import sqlite3
import zlib
from dataclasses import dataclass
from typing import Any, Iterator


_RE_LAST_UPDATED = re.compile(r'"lastUpdatedAt"\s*:\s*(\d+)')
_RE_CREATED_AT = re.compile(r'"createdAt"\s*:\s*(\d+)')


@dataclass
class VscdbSession:
    composer_id: str
    composer_data: dict[str, Any]
    bubble_entries: dict[str, dict[str, Any]]
    agent_kv_entries: dict[str, bytes]
    db_path: str


def iter_sessions(db_path: str) -> Iterator[VscdbSession]:
    composer_rows = _read_kv_rows(db_path, "composerData:")
    if not composer_rows:
        return
    agent_kv = _read_kv_rows(db_path, "agentKv:blob:")
    for key, raw in composer_rows.items():
        composer_id = key.removeprefix("composerData:")
        if not composer_id:
            continue
        parsed = _parse_json(raw)
        if parsed is None or not isinstance(parsed, dict):
            continue

        bubble_prefix = f"bubbleId:{composer_id}:"
        bubble_rows = _read_kv_rows(db_path, bubble_prefix)
        bubble_entries: dict[str, dict[str, Any]] = {}
        for bkey, braw in bubble_rows.items():
            bparsed = _parse_json(braw)
            if bparsed is not None and isinstance(bparsed, dict):
                bubble_entries[bkey] = bparsed

        yield VscdbSession(
            composer_id=composer_id,
            composer_data=parsed,
            bubble_entries=bubble_entries,
            agent_kv_entries=agent_kv,
            db_path=db_path,
        )


def scan_session_timestamps(db_path: str) -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            table = _resolve_table(conn)
            try:
                cursor = conn.execute(
                    f"""SELECT key,
                        COALESCE(
                            json_extract(value, '$.lastUpdatedAt'),
                            json_extract(value, '$.createdAt'),
                            0
                        )
                    FROM {table}
                    WHERE key LIKE 'composerData:%'
                      AND value IS NOT NULL"""
                )
                for key, ts in cursor:
                    composer_id = key.removeprefix("composerData:")
                    if composer_id and isinstance(ts, (int, float)) and ts:
                        result[composer_id] = int(ts)
            except sqlite3.OperationalError:
                cursor = conn.execute(
                    f"SELECT key, value FROM {table} WHERE key LIKE 'composerData:%' AND value IS NOT NULL"
                )
                for key, val in cursor:
                    composer_id = key.removeprefix("composerData:")
                    if not composer_id:
                        continue
                    text = val if isinstance(val, str) else _decompress_to_text(val)
                    ts = _extract_timestamp(text)
                    if ts:
                        result[composer_id] = ts
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        pass
    return result


def load_session(db_path: str, composer_id: str) -> VscdbSession | None:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            table = _resolve_table(conn)
            row = conn.execute(
                f"SELECT value FROM {table} WHERE key = ?",
                (f"composerData:{composer_id}",),
            ).fetchone()
            if row is None:
                return None
            val = row[0]
            if isinstance(val, str):
                val = val.encode("utf-8")
            parsed = _parse_json(val)
            if parsed is None or not isinstance(parsed, dict):
                return None

            bubble_prefix = f"bubbleId:{composer_id}:"
            bubble_cursor = conn.execute(
                f"SELECT key, value FROM {table} WHERE key LIKE ? || '%'",
                (bubble_prefix,),
            )
            bubble_entries: dict[str, dict[str, Any]] = {}
            for bkey, braw in bubble_cursor:
                if isinstance(braw, str):
                    braw = braw.encode("utf-8")
                bparsed = _parse_json(braw)
                if bparsed is not None and isinstance(bparsed, dict):
                    bubble_entries[bkey] = bparsed

            agent_kv_entries: dict[str, bytes] = {}
            conv_state = parsed.get("conversationState")
            hashes_to_load: list[str] = []
            if isinstance(conv_state, str) and conv_state:
                hashes_to_load = _extract_hashes(conv_state)
            elif isinstance(conv_state, dict):
                for value in conv_state.values():
                    if isinstance(value, str) and len(value) == 64:
                        hashes_to_load.append(value)

            for hash_value in hashes_to_load:
                agent_key = f"agentKv:blob:{hash_value}"
                arow = conn.execute(f"SELECT value FROM {table} WHERE key = ?", (agent_key,)).fetchone()
                if arow is not None:
                    aval = arow[0]
                    if isinstance(aval, str):
                        aval = aval.encode("utf-8")
                    agent_kv_entries[agent_key] = aval

            return VscdbSession(
                composer_id=composer_id,
                composer_data=parsed,
                bubble_entries=bubble_entries,
                agent_kv_entries=agent_kv_entries,
                db_path=db_path,
            )
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None


def read_item_table(db_path: str, key: str) -> str | None:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
            if row is None:
                return None
            val = row[0]
            if isinstance(val, bytes):
                return _decompress(val).decode("utf-8", errors="replace")
            return str(val)
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None


def _read_kv_rows(db_path: str, prefix: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            table = _resolve_table(conn)
            cursor = conn.execute(f"SELECT key, value FROM {table} WHERE key LIKE ? || '%'", (prefix,))
            for key, val in cursor:
                if val is None:
                    continue
                if isinstance(val, str):
                    val = val.encode("utf-8")
                result[key] = val
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        pass
    return result


def _resolve_table(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'"
        ).fetchone()
        if row:
            return "cursorDiskKV"
    except sqlite3.Error:
        pass
    return "ItemTable"


def _decompress_to_text(raw: bytes) -> str | None:
    if raw is None:
        return None
    try:
        return _decompress(raw).decode("utf-8", errors="replace")
    except (UnicodeDecodeError, ValueError):
        return None


def _extract_timestamp(text: str | None) -> int:
    if not text:
        return 0
    match = _RE_LAST_UPDATED.search(text) or _RE_CREATED_AT.search(text)
    return int(match.group(1)) if match else 0


def _decompress(raw: bytes) -> bytes:
    if len(raw) >= 2 and raw[0] == 0x78 and raw[1] in (0x01, 0x5E, 0x9C, 0xDA):
        try:
            return zlib.decompress(raw)
        except zlib.error:
            pass
    return raw


def _extract_hashes(conversation_state: str) -> list[str]:
    if not conversation_state:
        return []
    data_str = conversation_state.lstrip("~")
    if not data_str:
        return []
    padding = 4 - (len(data_str) % 4)
    if padding < 4:
        data_str += "=" * padding
    try:
        data = base64.b64decode(data_str)
    except Exception:
        return []
    return _walk_protobuf_for_hashes(data)


def _walk_protobuf_for_hashes(data: bytes) -> list[str]:
    hashes: list[str] = []
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _decode_varint(data, pos)
        except (IndexError, ValueError):
            break
        wire_type = tag & 0x07
        if wire_type == 0:
            try:
                _, pos = _decode_varint(data, pos)
            except (IndexError, ValueError):
                break
        elif wire_type == 2:
            try:
                field_len, pos = _decode_varint(data, pos)
            except (IndexError, ValueError):
                break
            if pos + field_len > len(data):
                break
            if field_len == 32:
                hashes.append(data[pos : pos + 32].hex())
            pos += field_len
        elif wire_type == 5:
            pos += 4
        elif wire_type == 1:
            pos += 8
        else:
            break
    return hashes


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise IndexError("Varint extends beyond data")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift >= 64:
            raise ValueError("Varint too long")
    return result, pos


def _parse_json(raw: bytes | None) -> Any | None:
    if raw is None:
        return None
    try:
        return json.loads(_decompress(raw).decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
