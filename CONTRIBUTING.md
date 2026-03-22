# Contributing

## Bootstrap

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install Chromium only when you need live browser runs:

```bash
playwright install chromium
```

## Common Commands

```bash
make lint
make test-unit
make coverage
make test-integration
make docs
```

Integration and network tests are opt-in:

```bash
RUN_INTEGRATION_TESTS=1 pytest --no-cov tests/integration
RUN_INTEGRATION_TESTS=1 RUN_NETWORK_TESTS=1 pytest --no-cov tests/integration
```

## Notes

- The default unit suite is offline and does not require Anthropic or Playwright.
- Coverage output is written to `reports/coverage/` and `reports/coverage.json`.
- Browser and network checks are intentionally separated so local iteration stays fast.
