# API Reference

All responses are JSON. Base URL: `http://localhost:8000`.

## `POST /analyze` — Upload trace files

Multipart form upload. Supports multiple files. Returns immediately with a `run_id`. Analysis runs in background.

### Request

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@session1.jsonl" \
  -F "file=@session2.jsonl"
```

Auto-detects source from file content. Override with query param:

```bash
curl -X POST "http://localhost:8000/analyze?source=claude_code" \
  -F "file=@session.jsonl"
```

Supported overrides: `claude_code`, `codex_cli`, `pi`.

### Response (202)

```json
{
  "run_id": "run_a3f7e2d1",
  "status": "pending",
  "message": "Analysis started",
  "session_count": 2
}
```

---

## `GET /runs/{run_id}` — Check run status

Poll this until `status` is `"done"`.

### Response

```json
{
  "run_id": "run_a3f7e2d1",
  "status": "done",
  "created_at": "2026-06-02T18:05:31.106757",
  "completed_at": "2026-06-02T18:05:37.927401",
  "stages": {
    "p0_normalize": {"status": "done", ...},
    "p1_classify":  {"status": "done", ...},
    "p2_context":   {"status": "done", ...},
    "p3_rca":       {"status": "done", ...},
    "p4a_behavior": {"status": "done", ...},
    "p4b_cluster":  {"status": "done", ...},
    "p4c_convention":{"status": "done", ...},
    "p5_aggregate": {"status": "done", ...},
    "p6_scope":     {"status": "done", ...}
  }
}
```

Stage status flow: `pending` → `running` → `done` | `error`.

### Error response

```json
{"status": "error", "error": "..."}
```

---

## `GET /runs/{run_id}/findings` — Filtered findings (recurring only)

Returns findings that appear across 2+ sessions.

```bash
curl http://localhost:8000/runs/run_a3f7e2d1/findings
```

### Response

```json
[
  {
    "session_id": "sess_abc123",
    "agents_md_rule": "Use specific error handling...",
    "category": "missing_context",
    "severity": 3,
    "is_recurring": true,
    "pattern_label": "error_handling",
    ...
  }
]
```

---

## `GET /runs/{run_id}/findings/all` — All findings

Same structure as `/findings` but includes:

- `total_findings`
- `severity_distribution`
- `category_distribution`
- `filtered_findings` (recurring subset)

---

## `GET /runs/{run_id}/stages/{stage_name}` — Raw stage output

Access any pipeline stage directly.

Available `stage_name` values:

| Stage | Content |
|-------|---------|
| `p0_normalize` | Normalized sessions with message counts |
| `p1_classify` | Per-session message classifications |
| `p2_context` | Context windows around trigger turns |
| `p3_rca` | Root-cause analysis results |
| `p4a_behavior` | Behavior rule classifications |
| `p4b_cluster` | Clustered pattern groups |
| `p4c_convention` | Convention analysis (dont_do / do_instead) |
| `p5_aggregate` | Full findings + metadata |
| `p6_scope` | Repo and developer mappings |

---

## `GET /health`

```bash
curl http://localhost:8000/health
```

### Response

```json
{"status": "ok", "model": "deepseek-v4-pro"}
```
