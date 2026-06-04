# Configuration

All configuration is via environment variables or a `.env` file in the project root.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | LLM API key |
| `OPENAI_BASE_URL` | No | `https://api.deepseek.com/v1` | LLM endpoint base URL |
| `MODEL` | No | `deepseek-v4-pro` | Model name |
| `CONCURRENCY` | No | `30` | Max concurrent LLM calls |
| `TEMP_DIR` | No | `/tmp/standalone-trace-analyzer` | Temp storage for run outputs |
| `BLACKBOX_API_URL` | No | `http://localhost:8000` | URL the CLI connects to |

## Example `.env`

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL=deepseek-v4-pro
CONCURRENCY=30
TEMP_DIR=/tmp/standalone-trace-analyzer
BLACKBOX_API_URL=http://localhost:8000
```

## Notes

- `OPENAI_BASE_URL` and `OPENAI_API_KEY` use OpenAI-compatible naming for compatibility with the client library, but any OpenAI-compatible provider works.
- `TEMP_DIR` must be writable. Stage outputs are saved as JSON files under `{TEMP_DIR}/runs/{run_id}/`.
- `CONCURRENCY` controls the `asyncio.Semaphore` limit on concurrent LLM requests. Lower this if you hit rate limits.
- `BLACKBOX_API_URL` is read by the CLI (`src/cli/client.py`). If the API is running on a different host or port, set this before launching the TUI.
