# tot_agent.tools

Claude API tool schema definitions and the `dispatch()` router.

## Tool inventory

| Tool name | Category | Description |
|---|---|---|
| `screenshot` | Vision | Capture a PNG of the active page |
| `navigate` | Navigation | Go to a URL or site-relative path |
| `click` | Interaction | Click a CSS selector or visible text |
| `fill` | Interaction | Type a value into an input field |
| `press_key` | Interaction | Press a keyboard key |
| `get_page_text` | Inspection | Return visible body text (≤ 4 000 chars) |
| `get_page_url` | Inspection | Return the current URL |
| `scroll_down` | Navigation | Scroll to the bottom of the page |
| `wait_for_element` | Synchronisation | Wait for a CSS selector to appear |
| `switch_user` | Context | Change the active browser session |
| `login` | Auth | Navigate to login and submit credentials |
| `fetch_book_covers` | Data | Search for book cover images |

## Dispatch flow

```mermaid
flowchart LR
    Claude -- "tool_use block" --> dispatch
    dispatch -- screenshot --> BrowserManager.screenshot
    dispatch -- navigate --> BrowserManager.navigate
    dispatch -- click --> BrowserManager.click
    dispatch -- fill --> BrowserManager.fill
    dispatch -- login --> BrowserManager.navigate & fill & press_key
    dispatch -- fetch_book_covers --> CoverFetcher.fetch
    dispatch -- "unknown tool" --> ErrorString["'ERROR: Unknown tool'"]
```

## Module reference

::: tot_agent.tools
    options:
      members:
        - TOOL_DEFINITIONS
        - dispatch
        - format_tool_result
