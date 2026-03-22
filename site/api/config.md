# tot_agent.config

Configuration dataclasses, environment variable loading, and runtime knobs.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `SITE_URL` | `http://localhost:4321` | Base URL of the target application |
| `AGENT_MODEL` | `claude-opus-4-5` | Claude model ID |
| `MAX_AGENT_STEPS` | `40` | Per-run tool-call iteration ceiling |
| `TOT_LOG_LEVEL` | `INFO` | CLI default log level |
| `TOT_LOG_FILE` | — | CLI default log file path |

## Module reference

::: tot_agent.config
    options:
      members:
        - SimUser
        - SIM_USERS
        - get_user
        - SITE_URL
        - ROUTES
        - ANTHROPIC_API_KEY
        - AGENT_MODEL
        - MAX_AGENT_STEPS
        - SCREENSHOT_WIDTH
        - SCREENSHOT_HEIGHT
        - OPEN_LIBRARY_SEARCH_URL
        - OPEN_LIBRARY_COVER_URL
        - GOOGLE_BOOKS_URL
        - COVER_SEARCH_QUERIES
