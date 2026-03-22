# Software Design

## 1. Introduction

`tot-agent` is an autonomous browser testing agent that combines Claude's vision and tool-use capabilities with a real Playwright browser to execute natural-language test scenarios against web applications.

This document describes the architectural decisions, design patterns, module structure, and key data flows that define the system.

---

## 2. Architectural overview

```mermaid
graph TB
    subgraph CLI Layer
        CLI["cli.py<br/>Click commands"]
    end
    subgraph Agent Layer
        Agent["agent.py<br/>BrowserAgent"]
        Goals["Goal templates<br/>CreateTestsGoal, VoteGoal…"]
        Observers["Observers<br/>ConsoleObserver, LoggingObserver"]
    end
    subgraph Infrastructure Layer
        Browser["browser.py<br/>BrowserManager"]
        Tools["tools.py<br/>TOOL_DEFINITIONS + dispatch()"]
        Covers["covers.py<br/>CoverFetcher + Sources"]
    end
    subgraph External
        Claude["Anthropic Claude API<br/>(vision + tool use)"]
        PW["Playwright / Chromium"]
        OL["Open Library API"]
        GB["Google Books API"]
    end

    CLI --> Agent
    CLI --> Goals
    Agent --> Claude
    Agent --> Tools
    Agent --> Observers
    Tools --> Browser
    Tools --> Covers
    Browser --> PW
    Covers --> OL
    Covers --> GB
```

---

## 3. Design patterns

### 3.1 Strategy — Cover sources

The `covers.py` module uses the **Strategy** pattern to make book-cover data sources interchangeable.

```mermaid
classDiagram
    class CoverSource {
        <<abstract>>
        +search(query, limit) list~BookCover~
    }
    class OpenLibrarySource {
        +search(query, limit) list~BookCover~
    }
    class GoogleBooksSource {
        +search(query, limit) list~BookCover~
    }
    class CoverFetcher {
        -_sources: list~CoverSource~
        +fetch(query, count) list~BookCover~
    }
    CoverSource <|-- OpenLibrarySource
    CoverSource <|-- GoogleBooksSource
    CoverFetcher o-- CoverSource
```

**Why:** Adding a new cover source (e.g. Amazon, Goodreads) requires only implementing `CoverSource.search()` and passing the instance to `CoverFetcher`.  No existing code needs to change.

### 3.2 Observer — Agent events

The `agent.py` module uses the **Observer** pattern to decouple the core loop from output concerns.

```mermaid
classDiagram
    class AgentObserver {
        <<abstract>>
        +on_event(event) None
    }
    class ConsoleObserver {
        +on_event(event) None
    }
    class LoggingObserver {
        +on_event(event) None
    }
    class BrowserAgent {
        -_observers: list~AgentObserver~
        +add_observer(obs) None
        +remove_observer(obs) None
        -_emit(event) None
        +run(goal) str
    }
    AgentObserver <|-- ConsoleObserver
    AgentObserver <|-- LoggingObserver
    BrowserAgent --> AgentObserver
```

**Why:** CI/CD pipelines need file-based logging; interactive use needs Rich terminal output; tests need neither.  Observers can be mixed and matched without modifying `BrowserAgent`.

### 3.3 Template Method — Goal builders

The `GoalTemplate` hierarchy applies the **Template Method** pattern to goal construction.

```mermaid
classDiagram
    class GoalTemplate {
        <<abstract>>
        +build(**kwargs) str
    }
    class CreateTestsGoal {
        +build() str
    }
    class VoteGoal {
        +build() str
    }
    class SimulateAllUsersGoal {
        +build() str
    }
    class FullSeedGoal {
        +build() str
    }
    GoalTemplate <|-- CreateTestsGoal
    GoalTemplate <|-- VoteGoal
    GoalTemplate <|-- SimulateAllUsersGoal
    GoalTemplate <|-- FullSeedGoal
```

**Why:** Goal strings follow a common structure (context + instructions + reporting request) but vary in specifics.  Sub-classes encapsulate the variation while the interface stays stable.

### 3.4 Context Object — BrowserManager

`BrowserManager` acts as a **Context Object**, encapsulating all Playwright state (browser instance, context pool, active user) behind a clean async API.  This isolates the agent and tool dispatcher from Playwright's async complexity.

---

## 4. Module dependency graph

```mermaid
graph LR
    cli --> agent
    cli --> config
    agent --> browser
    agent --> tools
    agent --> config
    tools --> browser
    tools --> covers
    covers --> config
    browser --> config
```

All modules depend only on the layer below them, preventing circular imports.

---

## 5. Agentic loop — sequence diagram

```mermaid
sequenceDiagram
    participant Agent as BrowserAgent.run()
    participant Claude as Anthropic API
    participant Dispatcher as tools.dispatch()
    participant Browser as BrowserManager
    participant Observer

    Agent->>Observer: emit(GOAL_START)
    loop Until end_turn or step limit
        Agent->>Observer: emit(STEP_START)
        Agent->>Claude: messages.create(history + tools)
        Claude-->>Agent: content blocks
        loop For each text block
            Agent->>Observer: emit(AGENT_TEXT)
        end
        loop For each tool_use block
            Agent->>Observer: emit(TOOL_CALL)
            Agent->>Dispatcher: dispatch(tool_name, input, bm)
            Dispatcher->>Browser: browser action
            Browser-->>Dispatcher: result
            Dispatcher-->>Agent: result
            Agent->>Observer: emit(TOOL_RESULT)
        end
        Agent->>Claude: tool_result messages
    end
    Agent->>Observer: emit(GOAL_COMPLETE or STEP_LIMIT)
```

---

## 6. Multi-user context model

Each simulated user gets an isolated Playwright `BrowserContext` with its own cookies and session storage.  Switching users is O(1) — contexts are lazily created and cached.

```mermaid
graph TB
    BM["BrowserManager"]
    C1["Context: admin<br/>(cookies, sessionStorage)"]
    C2["Context: alice<br/>(cookies, sessionStorage)"]
    C3["Context: bob<br/>(cookies, sessionStorage)"]
    BM --> C1
    BM --> C2
    BM --> C3
    P1["Page"] --> C1
    P2["Page"] --> C2
    P3["Page"] --> C3
```

---

## 7. Key design decisions

| Decision | Rationale |
|---|---|
| Vision-first (screenshots) over selector-based | Adapts to any UI; no maintenance when the app changes |
| Structured tool schemas | Claude can reason about available actions; schemas are validated by the API |
| Strategy for cover sources | Open/Closed principle — new sources don't require modifying the orchestrator |
| Observer for agent output | Separates concerns; tests can use a no-op observer |
| `dataclass` for `SimUser` | Zero-boilerplate, auto-generated `__eq__` and `__repr__`, IDE-friendly |
| `pyproject.toml` over `setup.py` | PEP 517/518 modern packaging standard |
| `src` layout | Prevents accidental imports of non-installed code during development |

---

## 8. Error handling strategy

| Layer | Approach |
|---|---|
| Browser actions | Return `"ERROR: ..."` strings rather than raising; the agent can read and recover |
| Cover sources | Catch `httpx.HTTPError`, log a warning, return empty list |
| Agent loop | Tool errors are fed back to Claude as text; Claude decides how to recover |
| CLI | Click's `BadParameter` for invalid user input; unhandled exceptions propagate |

---

## 9. Testing strategy

```mermaid
pyramid
    accTitle: Test pyramid
    accDescr: Unit tests form the base; integration tests are fewer
    section Unit (fast, offline)
        "config — SimUser, routes, env vars" : 15
        "covers — strategy pattern, HTTP mocking" : 20
        "browser — async mock, BrowserManager" : 18
        "tools — dispatch routing, format_tool_result" : 14
        "agent — observer pattern, loop logic" : 16
    section Integration (real browser / network)
        "BrowserManager — live Chromium" : 4
        "CoverFetcher — live Open Library" : 2
```

All external HTTP calls in unit tests are intercepted with `respx`.  Browser tests use `pytest-asyncio` with a `live_browser` fixture that spins up real Chromium (skipped by default in CI via `SKIP_INTEGRATION=1`).
