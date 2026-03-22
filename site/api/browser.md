# tot_agent.browser

Playwright browser context pool.

## Class diagram

```mermaid
classDiagram
    class BrowserManager {
        +headless: bool
        +site_url: str
        -_pw: Playwright
        -_browser: Browser
        -_contexts: dict
        -_active_user: str
        +__aenter__() BrowserManager
        +__aexit__(*_) None
        +switch_user(user_key) dict
        +active_page() Page
        +active_user() str
        +navigate(url) dict
        +screenshot() str
        +click(selector) dict
        +fill(selector, value) dict
        +select_option(selector, value) dict
        +get_page_text() dict
        +get_page_url() dict
        +wait_for_selector(selector, timeout) dict
        +wait_for_page_ready() dict
        +press_key(key) dict
        +scroll_down() dict
        +evaluate(js) dict
        +upload_file(selector, file_path) dict
    }
```

## Context lifecycle

```mermaid
stateDiagram-v2
    [*] --> Stopped
    Stopped --> Running : __aenter__()
    Running --> Active : switch_user()
    Active --> Active : navigate() / click() / fill() / …
    Active --> Running : switch_user() (different user)
    Running --> Stopped : __aexit__()
```

## Structured results

All action methods return a `dict` with a consistent shape produced by helpers
in `results.py`:

| Key | Type | Description |
|---|---|---|
| `ok` | `bool` | `True` on success, `False` on failure |
| `message` | `str` | Human-readable summary |
| `data` | `dict` | Method-specific payload (e.g. `{"url": "..."}`) |
| `error` | `str` | Error detail (only present when `ok` is `False`) |
| `recoverable` | `bool` | `True` when a timeout or transient error occurred |

## Module reference

::: tot_agent.browser
    options:
      members:
        - BrowserManager
