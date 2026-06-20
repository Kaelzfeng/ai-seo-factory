# Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `development` | development / production |
| `SECRET_KEY` | **Yes (prod)** | `dev-secret...` | Flask secret key |
| `SQLITE_PATH` | No | `data/app.db` | SQLite database path |
| `LLM_PROVIDER` | No | auto-detect | mock / anthropic / deepseek / openai |
| `LLM_MODEL` | No | (per role) | Override default model |
| `LLM_TIMEOUT` | No | `45` | LLM request timeout (seconds) |
| `LLM_MAX_RETRIES` | No | `2` | Max retries for LLM calls |
| `DEEPSEEK_API_KEY` | No | - | DeepSeek API key |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key |
| `OPENAI_API_KEY` | No | - | OpenAI API key |

### Provider Auto-Detection

If `LLM_PROVIDER` is not set, the system auto-detects:
1. `DEEPSEEK_API_KEY` set → `deepseek`
2. `OPENAI_API_KEY` set → `openai`
3. Neither → falls back to `anthropic` (needs ANTHROPIC_API_KEY) or `mock` (no keys)

### Switching Provider

```bash
export LLM_PROVIDER=deepseek   # Use DeepSeek
export LLM_PROVIDER=openai     # Use OpenAI
export LLM_PROVIDER=mock       # Use mock (no API key needed)
```

### Default Models by Role

| Provider | Planner (cheap) | Writer (strong) | Polish (cheap) |
|---|---|---|---|
| anthropic | claude-haiku-4-5 | claude-sonnet-4-6 | claude-haiku-4-5 |
| deepseek | deepseek-v4-flash | deepseek-v4-pro | deepseek-v4-flash |
| openai | gpt-4o-mini | gpt-4o | gpt-4o-mini |
| mock | mock | mock | mock |
| `SERP_PROVIDER` | No | `mock` | mock / manual / google_cse |
| `WORDPRESS_BASE_URL` | No | - | WordPress REST API URL |
| `WORDPRESS_USERNAME` | No | - | WordPress username |
| `WORDPRESS_APP_PASSWORD` | No | - | WordPress app password |
| `WEBHOOK_URL` | No | - | Webhook endpoint URL |
| `CACHE_DIR` | No | `.cache` | Disk cache directory |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `PORT` | No | `5000` | Flask port |

## Security Notes

- Never commit `.env` to git
- Rotate SECRET_KEY in production
- Use app passwords for WordPress, not main account passwords
- API keys are never printed in logs (masked)
