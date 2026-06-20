# Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `development` | development / production |
| `SECRET_KEY` | **Yes (prod)** | `dev-secret...` | Flask secret key |
| `SQLITE_PATH` | No | `data/app.db` | SQLite database path |
| `LLM_PROVIDER` | No | auto-detect | anthropic / deepseek |
| `DEEPSEEK_API_KEY` | No | - | DeepSeek API key |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key |
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
