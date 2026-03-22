# tot-agent

**Autonomous browser agent for scripted GUI testing.**

`tot-agent` drives a real [Playwright](https://playwright.dev/) browser with [Claude](https://www.anthropic.com/claude) vision + tool-use to execute natural-language test scenarios against any web application.  It was originally built to seed and test the *This-or-That* A/B book-cover testing platform.

```
Claude (vision + tool use)
   |
   | screenshot / click / fill / navigate
   v
Playwright browser  <-->  your local web app
   +
Open Library / Google Books  -->  real book cover images
```

**Full documentation:** [mattbriggs.github.io/this-or-that-agent](https://mattbriggs.github.io/this-or-that-agent)

---

## Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/mattbriggs/this-or-that-agent
cd this-or-that-agent
python -m venv .venv && source .venv/bin/activate

# 2. Install package (add [dev] for tests + docs tools)
pip install -e ".[dev]"

# 3. Install Playwright browsers only if you need live browser runs
playwright install chromium

# 4. Configure
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

---

## Quick start

```bash
# Verify setup
tot-agent --version
tot-agent info

# Create 5 A/B tests (requires your dev site to be running)
tot-agent seed --tests 5

# Preview book covers without launching a browser
tot-agent covers "mystery thriller" --count 3

# Run a custom goal
tot-agent goal "Log in as admin and take a screenshot of the dashboard."
```

---

## CLI commands

| Command | Description |
|---|---|
| `tot-agent create` | Create A/B tests with real book covers |
| `tot-agent vote` | Have a single simulated user vote |
| `tot-agent simulate` | Simulate all configured users voting |
| `tot-agent seed` | Full pipeline: create tests + simulate voting + view results |
| `tot-agent goal TEXT` | Execute a custom natural-language goal |
| `tot-agent users` | List configured simulated users |
| `tot-agent info` | Show runtime configuration |
| `tot-agent covers QUERY` | Preview book covers (no browser needed) |

All commands accept global options — see `tot-agent --help` or the [Usage Guide](https://mattbriggs.github.io/this-or-that-agent/usage/).

---

## Running tests

```bash
# Fast offline unit tests
make test-unit

# Coverage report for the offline suite
make coverage
open reports/coverage/index.html

# Opt-in Playwright integration tests
RUN_INTEGRATION_TESTS=1 pytest --no-cov tests/integration

# Opt-in live network tests as well
RUN_INTEGRATION_TESTS=1 RUN_NETWORK_TESTS=1 pytest --no-cov tests/integration
```

Developer workflow details live in [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Building docs

```bash
mkdocs serve          # live-reload dev server at http://127.0.0.1:8000
mkdocs build          # build HTML to /docs for GitHub Pages
```

---

## Project layout

```
this-or-that-agent/
├── src/
│   └── tot_agent/
│       ├── __init__.py     # package version
│       ├── agent.py        # BrowserAgent + Observer pattern + Goal templates
│       ├── browser.py      # Playwright multi-context BrowserManager
│       ├── cli.py          # Click CLI entry point
│       ├── config.py       # SimUser, ROUTES, env vars
│       ├── covers.py       # Strategy pattern cover fetching
│       ├── results.py      # Structured browser/tool action results
│       └── tools.py        # Claude tool schemas + dispatcher
├── tests/
│   ├── conftest.py         # shared fixtures
│   ├── unit/               # fast offline unit tests
│   └── integration/        # Playwright + live network tests
├── CONTRIBUTING.md         # developer setup and common commands
├── Makefile                # lint/test/coverage/docs task shortcuts
├── site/                   # MkDocs markdown source
│   ├── design/             # SRS, software design, roadmap
│   └── api/                # auto-generated API reference pages
├── docs/                   # MkDocs HTML output (GitHub Pages)
├── reports/                # test coverage HTML output
├── pyproject.toml          # packaging, dependencies, tool config
├── mkdocs.yml              # documentation site configuration
└── .env.example            # environment variable template
```

---

## Design highlights

- **Strategy pattern** — book-cover sources are interchangeable (`OpenLibrarySource`, `GoogleBooksSource`); add new sources without touching orchestration code.
- **Observer pattern** — attach `ConsoleObserver`, `LoggingObserver`, or your own reporter to the agent loop without modifying `BrowserAgent`.
- **Template Method pattern** — pre-built goal classes (`CreateTestsGoal`, `VoteGoal`, `FullSeedGoal`) share a common structure and are easy to extend.
- **Structured tool results** — browser and dispatch layers return machine-readable success/error payloads, which makes retries and diagnostics more reliable.
- **Vision-first** — the agent reads screenshots rather than hardcoded selectors, so it adapts to UI changes automatically.

See the [Software Design](https://mattbriggs.github.io/this-or-that-agent/design/software-design/) doc for full architecture diagrams.

---

## License

MIT
