# Software Design

## 1. Introduction

`tot-agent` is a browser-driving test tool that combines two execution modes:
an **agentic mode** powered by Claude vision + tool-use, and a **scripted mode**
that executes a deterministic step sequence with no LLM involvement.  Both
modes share the same Playwright infrastructure (`BrowserManager`) and cover-
fetching layer (`CoverFetcher`).

The system was originally built for the *This-or-That* A/B book-cover testing
platform and is designed to retarget any web GUI by swapping a single
configuration object.

This document describes the architectural decisions, design patterns, module
structure, and key data flows that define the system.

---

## 2. Architectural overview

```mermaid
graph TB
    subgraph CLI Layer
        CLI["cli.py\nClick commands"]
    end

    subgraph Scripted Layer
        Flow["flow.py\nContestCreationFlow"]
        Platform["platform.py\nPlatformConfig"]
    end

    subgraph Agent Layer
        Agent["agent.py\nBrowserAgent"]
        Goals["Goal templates\nCreateTestsGoal, VoteGoal…"]
        Observers["Observers\nConsoleObserver, LoggingObserver"]
    end

    subgraph Infrastructure Layer
        Browser["browser.py\nBrowserManager"]
        Tools["tools.py\nTOOL_DEFINITIONS + dispatch()"]
        Covers["covers.py\nCoverFetcher + Sources"]
        Results["results.py\nAction result helpers"]
    end

    subgraph External
        Claude["Anthropic Claude API\n(vision + tool use)"]
        PW["Playwright / Chromium"]
        OL["Open Library API"]
        GB["Google Books API"]
    end

    CLI --> Flow
    CLI --> Agent
    CLI --> Goals
    Flow --> Platform
    Flow --> Browser
    Flow --> Covers
    Agent --> Claude
    Agent --> Tools
    Agent --> Observers
    Tools --> Browser
    Tools --> Covers
    Browser --> Results
    Browser --> PW
    Covers --> OL
    Covers --> GB
```

---

## 3. Two execution modes

### 3.1 Agentic mode

Claude receives a goal string and drives the browser through a tool-use loop.
After each action the agent takes a screenshot and decides the next step.

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
        loop For each tool_use block
            Agent->>Observer: emit(TOOL_CALL)
            Agent->>Dispatcher: dispatch(tool_name, input, bm)
            Dispatcher->>Browser: browser action
            Browser-->>Dispatcher: result dict
            Dispatcher-->>Agent: result
            Agent->>Observer: emit(TOOL_RESULT)
        end
        Agent->>Claude: tool_result messages
    end
    Agent->>Observer: emit(GOAL_COMPLETE or STEP_LIMIT)
```

**When to use:** Exploratory testing, variable or open-ended goals, any
scenario where the UI structure is not fully known in advance.

**Cost:** Every browser interaction requires at least one Claude API call.
Open-ended goals can trigger many loop iterations.

### 3.2 Scripted mode

The flow is a fixed Python sequence.  No LLM is involved.  Each step calls
`BrowserManager` directly and checks its structured result dict immediately.

```mermaid
sequenceDiagram
    participant Flow as ContestCreationFlow
    participant Covers as CoverFetcher
    participant OL as Open Library / Google Books
    participant Browser as BrowserManager

    Flow->>Covers: fetch_random_pairs(1)
    Covers->>OL: HTTP search + image download
    OL-->>Covers: BookCover pair + bytes
    Covers-->>Flow: ContestData

    Flow->>Browser: switch_user(username)
    Flow->>Browser: navigate(login_route) + fill + click
    Browser-->>Flow: {"ok": true}
    Flow->>Browser: navigate(create_route)
    Flow->>Browser: fill(title), fill(description), fill(labels), fill(tags)
    Flow->>Browser: set_input_files[0], set_input_files[1]
    Flow->>Browser: click(submit)
    Browser-->>Flow: {"ok": true}
    Flow->>Browser: get_page_url() → verify redirect
    Flow->>Browser: click(logout)
```

**When to use:** Repetitive, well-defined flows like contest creation.
Zero API cost.  Deterministic — same code path every run.

**How to target a new platform:** Write a `PlatformConfig` instance with
the correct routes and selectors.  The flow itself does not change.

---

## 4. Design patterns

### 4.1 Strategy — Cover sources

The `covers.py` module uses the **Strategy** pattern to make book-cover data
sources interchangeable.

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
        -_sources list~CoverSource~
        +fetch(query, count) list~BookCover~
        +fetch_random_pairs(n) list~tuple~
    }
    CoverSource <|-- OpenLibrarySource
    CoverSource <|-- GoogleBooksSource
    CoverFetcher o-- CoverSource
```

**Why:** Adding a new cover source (e.g. Amazon, Goodreads) requires only
implementing `CoverSource.search()` and passing the instance to `CoverFetcher`.
No existing code changes.

### 4.2 Observer — Agent events

The `agent.py` module uses the **Observer** pattern to decouple the core loop
from output concerns.

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
        -_observers list~AgentObserver~
        +add_observer(obs) None
        +remove_observer(obs) None
        -_emit(event) None
        +run(goal) str
    }
    AgentObserver <|-- ConsoleObserver
    AgentObserver <|-- LoggingObserver
    BrowserAgent --> AgentObserver
```

**Why:** CI/CD pipelines need file-based logging; interactive use needs Rich
terminal output; tests need neither.  Observers can be mixed and matched
without modifying `BrowserAgent`.

### 4.3 Template Method — Goal builders

The `GoalTemplate` hierarchy applies the **Template Method** pattern to goal
string construction.

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

**Why:** Goal strings follow a common structure but vary in specifics.
Sub-classes encapsulate the variation while the interface stays stable.

### 4.4 Context Object — BrowserManager

`BrowserManager` acts as a **Context Object**, encapsulating all Playwright
state (browser instance, context pool, active user) behind a clean async API.
This isolates both the agent loop and the scripted flow from Playwright's
async complexity.

### 4.5 Configuration Object — PlatformConfig

`PlatformConfig` is a plain data class that declares the routes and CSS
selectors for a specific web platform's login and contest-creation UI.  The
scripted flow (`ContestCreationFlow`) reads all values from this object and
contains no hardcoded selectors.

```mermaid
classDiagram
    class PlatformConfig {
        +name str
        +login_route str
        +create_route str
        +email_selector str
        +password_selector str
        +title_selector str
        +file_input_selector str
        +image_a_file_nth int
        +image_b_file_nth int
        +logout_selector str
    }
    class ContestCreationFlow {
        -bm BrowserManager
        -platform PlatformConfig
        +run_for_user(user) bool
        -_research_phase() ContestData
        -_browser_phase(user, data) bool
    }
    ContestCreationFlow --> PlatformConfig
    ContestCreationFlow --> BrowserManager
```

**Why:** Retargeting the scripted flow to a new SaaS platform requires only
a new `PlatformConfig` instance.  All route navigation, form filling, file
upload indexing, and logout behavior are driven by the config alone.

---

## 5. Module dependency graph

```mermaid
graph LR
    cli --> agent
    cli --> flow
    cli --> config
    flow --> platform
    flow --> browser
    flow --> covers
    flow --> results
    agent --> browser
    agent --> tools
    agent --> config
    tools --> browser
    tools --> covers
    covers --> config
    browser --> config
    browser --> results
```

All modules depend only on the layer below them.  `flow` and `agent` are
siblings — neither depends on the other — which means the scripted and agentic
paths can evolve independently.

---

## 6. Multi-user context model

Each simulated user gets an isolated Playwright `BrowserContext` with its own
cookies and session storage.  Switching users is O(1) — contexts are lazily
created and cached.  Both execution modes use the same pool.

```mermaid
graph TB
    BM["BrowserManager"]
    C1["Context: test1\n(cookies, sessionStorage)"]
    C2["Context: test2\n(cookies, sessionStorage)"]
    C3["Context: test3\n(cookies, sessionStorage)"]
    BM --> C1
    BM --> C2
    BM --> C3
    P1["Page"] --> C1
    P2["Page"] --> C2
    P3["Page"] --> C3
```

The scripted flow calls `switch_user()` at the start of each run and logs out
at the end, so subsequent users start from a clean state.

---

## 7. Key design decisions

| Decision | Rationale |
|---|---|
| Two execution modes | Scripted mode eliminates token cost for repetitive flows; agentic mode handles variable goals |
| PlatformConfig as plain data | Retargeting to a new SaaS requires no logic changes — only a new config instance |
| Scripted flow stops on first failure | No retry loop means no token spiral and predictable failure signals |
| Vision-first in agentic mode | Adapts to any UI; no maintenance when the app layout changes |
| Structured result dicts (`{"ok": bool}`) | Both modes check the same contract — consistent error handling across agentic and scripted paths |
| Strategy for cover sources | Open/Closed principle — new sources don't require modifying the orchestrator |
| Observer for agent output | Separates concerns; tests can use a no-op observer |
| `src` layout | Prevents accidental imports of non-installed code during development |

---

## 8. Error handling strategy

| Layer | Approach |
|---|---|
| Scripted flow steps | Check `{"ok": bool}` result dict; log and return `False` on first failure |
| Agentic browser actions | Return `{"ok": false, ...}` dicts; Claude reads them and decides how to recover |
| Cover sources | Catch `httpx.HTTPError`, log a warning, return empty list; fall through to next source |
| File upload (scripted) | Index bounds check before `set_input_files`; logs count mismatch and returns `False` |
| Logout (scripted) | Non-fatal — logged as a warning; does not fail the run |
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
        "platform — PlatformConfig field defaults" : 6
        "flow — research phase, step sequencing" : 18
        "browser — async mock, BrowserManager" : 18
        "tools — dispatch routing, format_tool_result" : 14
        "agent — observer pattern, loop logic" : 16
    section Integration (real browser / network)
        "BrowserManager — live Chromium" : 4
        "CoverFetcher — live Open Library" : 2
        "ContestCreationFlow — live app + browser" : 2
```

All external HTTP calls in unit tests are intercepted with `respx`.  Browser
tests use `pytest-asyncio` with a `live_browser` fixture that spins up real
Chromium (skipped by default in CI via `SKIP_INTEGRATION=1`).

Flow unit tests mock `BrowserManager` and `CoverFetcher` so the step sequence
can be verified without a running browser or live API.
