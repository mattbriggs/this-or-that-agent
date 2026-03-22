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

### Browser timeout variables

| Variable | Default | Description |
|---|---|---|
| `NAVIGATION_TIMEOUT_MS` | `30000` | Playwright page navigation timeout (ms) |
| `ACTION_TIMEOUT_MS` | `10000` | Playwright element action timeout (ms) |
| `WAIT_FOR_ELEMENT_TIMEOUT_MS` | `15000` | `wait_for_selector` timeout (ms) |
| `PAGE_READY_TIMEOUT_MS` | `10000` | `wait_for_load_state` timeout (ms) |

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
        - NAVIGATION_TIMEOUT_MS
        - ACTION_TIMEOUT_MS
        - WAIT_FOR_ELEMENT_TIMEOUT_MS
        - PAGE_READY_TIMEOUT_MS
        - SCREENSHOT_WIDTH
        - SCREENSHOT_HEIGHT
        - OPEN_LIBRARY_SEARCH_URL
        - OPEN_LIBRARY_COVER_URL
        - GOOGLE_BOOKS_URL
        - COVER_SEARCH_QUERIES
