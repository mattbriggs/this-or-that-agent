# Test Report

**Date:** 2026-03-21
**Python:** 3.12.7
**pytest:** 8.2.0
**Environment:** macOS (darwin)

---

## Summary

| Metric | Value |
|---|---|
| Tests collected | 124 |
| Passed | 118 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 6 |
| Overall result | **PASS** |

Skipped tests are the opt-in integration and live-network checks in
`tests/integration/`.

---

## Coverage Summary

| Module | Statements | Missed | Coverage |
|---|---|---|---|
| `tot_agent/__init__.py` | 4 | 0 | **100%** |
| `tot_agent/agent.py` | 191 | 6 | **97%** |
| `tot_agent/browser.py` | 145 | 11 | **92%** |
| `tot_agent/cli.py` | 142 | 20 | **86%** |
| `tot_agent/config.py` | 55 | 0 | **100%** |
| `tot_agent/covers.py` | 118 | 1 | **99%** |
| `tot_agent/results.py` | 25 | 0 | **100%** |
| `tot_agent/tools.py` | 74 | 3 | **96%** |
| **TOTAL** | **754** | **41** | **95%** |

Artifacts:

- HTML: `reports/coverage/index.html`
- JSON: `reports/coverage.json`

---

## Notes

- The default unit suite is now fully offline.
- Anthropic and Playwright are no longer required just to import pure modules or run unit tests.
- Integration and live-network tests are explicit opt-in runs via `RUN_INTEGRATION_TESTS=1` and `RUN_NETWORK_TESTS=1`.
