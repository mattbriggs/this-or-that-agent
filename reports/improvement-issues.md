# Improvement Issues

## Phase 1: Developer Setup

1. Remove forced coverage from default `pytest` runs.
2. Document one supported bootstrap path and common commands.
3. Add a simple task runner for lint, unit tests, integration tests, and coverage.

## Phase 2: Dependency Boundaries

4. Lazy-load Anthropic so pure goal/event imports do not require the SDK.
5. Lazy-load Playwright so browser-adjacent unit tests can run without Chromium bindings installed.
6. Keep the agent constructor testable by allowing a client to be injected.

## Phase 3: Runtime Safety

7. Replace free-form error strings with structured tool results.
8. Stop the login flow on failed substeps instead of always returning success.
9. Run model calls without blocking the event loop.

## Phase 4: Browser Reliability

10. Replace brittle `networkidle` navigation waits with explicit DOM-ready waits.
11. Replace fixed post-submit sleeps with best-effort readiness checks.
12. Centralize browser timeout configuration.

## Phase 5: Verification

13. Keep the default test suite fully offline.
14. Replace `respx`-based tests with direct `httpx` patching at the call site.
15. Add CLI coverage with `CliRunner`.
16. Make integration and live-network tests explicit opt-in runs.

## Phase 6: Cleanup

17. Clean up remaining lint issues in source and tests.
18. Surface runtime timeout settings in `tot-agent info`.
19. Produce a coverage report from the offline test suite.
