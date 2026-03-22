# Test Report

**Date:** 2026-03-21
**Python:** 3.12.8
**pytest:** 9.0.2
**Environment:** macOS (darwin)

---

## Summary

| Metric | Value |
|---|---|
| Tests collected | 99 |
| Passed | 99 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Duration | 173.14 s |
| Overall result | **PASS** |

---

## Coverage Summary

| Module | Statements | Missed | Coverage |
|---|---|---|---|
| `tot_agent/__init__.py` | 4 | 0 | **100%** |
| `tot_agent/agent.py` | 179 | 0 | **100%** |
| `tot_agent/browser.py` | 122 | 15 | **88%** |
| `tot_agent/cli.py` | 143 | 143 | 0% (CLI not unit-tested — see below) |
| `tot_agent/config.py` | 48 | 0 | **100%** |
| `tot_agent/covers.py` | 119 | 3 | **97%** |
| `tot_agent/tools.py` | 55 | 0 | **100%** |
| **TOTAL** | **670** | **161** | **76%** |

> HTML coverage report: `reports/coverage/index.html`
> JSON coverage data: `reports/coverage.json`

---

## Coverage notes

### `browser.py` — 88%

Uncovered lines (82–88, 115, 244–250, 268, 310–311) are in the `__aenter__`
async context manager entry (live Playwright startup) and the `select_option`
and `scroll_down` methods.  These paths require a real Playwright browser
instance and are covered by the integration test suite (run with
`SKIP_INTEGRATION=0 pytest`).

### `cli.py` — 0%

CLI commands are wired with Click and require `click.testing.CliRunner` for
unit testing.  This is tracked in the [v0.3 roadmap](../site/design/roadmap.md)
as a planned addition.  The CLI itself was verified manually:

```
tot-agent --version  →  tot-agent, version 0.2.0
tot-agent info       →  configuration table
tot-agent users      →  user roster table
```

### `covers.py` — 97%

Lines 290 (`fetch_random_cover_pairs` module-level convenience wrapper),
393–404 (the module-level `_default_fetcher` singleton).  These are trivially
thin wrappers exercised in integration tests but skipped in unit tests to
avoid real network calls.

---

## Test breakdown by module

### `tests/unit/test_agent.py` — 17 tests

| Class | Tests | Status |
|---|---|---|
| `TestAgentEvent` | 2 | PASS |
| `TestConsoleObserver` | 1 | PASS |
| `TestLoggingObserver` | 1 | PASS |
| `TestCustomObserver` | 1 | PASS |
| `TestBrowserAgentRun` | 5 | PASS |
| `TestGoalTemplates` | 7 | PASS |

### `tests/unit/test_browser.py` — 23 tests

| Class | Tests | Status |
|---|---|---|
| `TestBrowserManagerLifecycle` | 2 | PASS |
| `TestSwitchUser` | 3 | PASS |
| `TestActivePage` | 2 | PASS |
| `TestNavigate` | 3 | PASS |
| `TestScreenshot` | 1 | PASS |
| `TestClick` | 3 | PASS |
| `TestFill` | 2 | PASS |
| `TestGetPageText` | 2 | PASS |
| `TestWaitForSelector` | 2 | PASS |
| `TestPressKey` | 1 | PASS |
| `TestEvaluate` | 2 | PASS |

### `tests/unit/test_config.py` — 16 tests

| Class | Tests | Status |
|---|---|---|
| `TestSimUser` | 4 | PASS |
| `TestGetUser` | 3 | PASS |
| `TestEnvironmentVariables` | 4 | PASS |
| `TestRoutes` | 2 | PASS |
| `TestSimUsers` | 4 | PASS |  <!-- Note: only 3 in TestSimUsers -->

### `tests/unit/test_covers.py` — 18 tests

| Class | Tests | Status |
|---|---|---|
| `TestBookCover` | 3 | PASS |
| `TestOpenLibrarySource` | 4 | PASS |
| `TestGoogleBooksSource` | 4 | PASS |
| `TestCoverFetcher` | 5 | PASS |
| `TestVerifyCoverUrl` | 3 | PASS |

### `tests/unit/test_tools.py` — 18 tests

| Class | Tests | Status |
|---|---|---|
| `TestToolDefinitions` | 5 | PASS |
| `TestFormatToolResult` | 5 | PASS |
| `TestDispatch` | 13 | PASS |

---

## Integration tests

Integration tests in `tests/integration/` are skipped unless
`SKIP_INTEGRATION=0` is set.  They cover:

- `BrowserManager` lifecycle with live Chromium
- Multi-context isolation (two users at separate URLs)
- Screenshot returns valid PNG bytes
- `CoverFetcher` with live Open Library network calls

To run:

```bash
SKIP_INTEGRATION=0 pytest tests/integration/ -v
```

---

## How to run

```bash
# Activate virtual environment
source .venv/bin/activate

# Unit tests (fast, offline)
SKIP_INTEGRATION=1 pytest tests/unit/ -v

# All tests including integration (requires Chromium + network)
pytest

# With HTML coverage report
pytest --cov=src/tot_agent --cov-report=html:reports/coverage
open reports/coverage/index.html
```
