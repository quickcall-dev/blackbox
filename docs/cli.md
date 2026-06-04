# CLI Guide

The `quickcall` TUI provides an interactive interface for selecting sessions, running analysis, and viewing results.

## Installation

```bash
uv run quickcall
```

Or if installed globally:

```bash
quickcall
```

## Screen flow

### Splash

Shows **"QuickCall  Blackbox"** centered, then auto-advances to the browser.

| Key | Action |
|-----|--------|
| Any key | Advance immediately |

### Browser

DataTable with discovered sessions from `~/.claude`, `~/.codex`, `~/.pi`.

| Key | Action |
|-----|--------|
| `Space` | Select / deselect session |
| `Ctrl+A` | Submit selected sessions for analysis |
| `1` | Toggle Claude source filter |
| `2` | Toggle Codex source filter |
| `3` | Toggle pi source filter |
| `q` | Quit |

### Progress

Shown while analysis runs. Left pane lists stages (P0–P6) with `✓` for done and `*` for running. Right pane shows live output of the selected stage.

| Key | Action |
|-----|--------|
| `↑ / ↓` | Navigate between stages (works while running) |
| `PgUp / PgDn` | Scroll right pane |
| `Ctrl+P` | Command palette |
| `q` | Quit |

**Auto-follow:** cursor snaps to the latest completed stage as the pipeline runs.

### Results

Shows the findings summary once analysis completes.

| Key | Action |
|-----|--------|
| `↑ / ↓` | Navigate findings |
| `PgUp / PgDn` | Scroll detail pane |
| `q` | Quit |

## Navigation during analysis

You can navigate between stages while the pipeline is running. The left pane updates in real time as stages complete. Use `↑ / ↓` to inspect earlier stage outputs without interrupting the background task.
