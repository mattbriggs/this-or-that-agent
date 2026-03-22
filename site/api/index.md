# API Reference

Auto-generated documentation for all `tot_agent` modules.

```mermaid
graph TD
    CLI["cli.py<br/>Click CLI entry point"] --> Agent["agent.py<br/>BrowserAgent + Goal templates"]
    CLI --> Config["config.py<br/>SimUser, ROUTES, env vars"]
    Agent --> Browser["browser.py<br/>BrowserManager"]
    Agent --> Tools["tools.py<br/>TOOL_DEFINITIONS + dispatch()"]
    Agent --> Config
    Tools --> Browser
    Tools --> Covers["covers.py<br/>CoverFetcher + Sources"]
    Tools --> Results["results.py<br/>ActionResult helpers"]
    Browser --> Results
    Covers --> Config
```

| Module | Description |
|---|---|
| [agent](agent.md) | Core agentic loop, Observer pattern, Goal templates |
| [browser](browser.md) | Playwright browser context pool |
| [covers](covers.md) | Book cover fetching with Strategy pattern |
| [tools](tools.md) | Claude tool schemas and dispatcher |
| [results](results.md) | Structured action result helpers |
| [config](config.md) | Configuration, SimUser, env vars |
| [cli](cli.md) | Click CLI commands |
