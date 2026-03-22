# Usage Guide

All commands are available through the `tot-agent` entry point installed by
`pip install -e .`.

---

## Global options

These options apply to every sub-command and are placed **before** the
sub-command name:

```
tot-agent [OPTIONS] COMMAND [ARGS]...
```

| Option | Default | Description |
|---|---|---|
| `--version` | — | Print version and exit |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--log-file PATH` | — | Write logs to a file in addition to stderr |
| `--model MODEL` | `claude-opus-4-5` | Override Claude model ID |
| `--max-steps N` | `40` | Override per-run iteration ceiling |
| `--site-url URL` | `http://localhost:4321` | Override target application base URL |

```bash
# Enable debug logging and write to a file
tot-agent --log-level DEBUG --log-file run.log seed --tests 3
```

---

## Commands

### `create` — Create A/B tests

Create A/B tests using real book covers fetched from Open Library.

```bash
tot-agent create --count 5
tot-agent create --count 3 --genre "horror"
tot-agent create --count 2 --genre "fantasy" --headless
```

| Option | Default | Description |
|---|---|---|
| `--count N` | `5` | Number of A/B tests to create |
| `--genre TEXT` | `mixed` | Book genre; `"mixed"` samples a variety |
| `--headless` | `false` | Hide the browser window |

---

### `vote` — Single user voting

Have one simulated user vote on existing A/B tests.

```bash
tot-agent vote --user alice --count 3
tot-agent vote --user bob --count 5 --headless
```

| Option | Default | Description |
|---|---|---|
| `--user TEXT` | required | Username (must exist in `SIM_USERS`) |
| `--count N` | `3` | Number of tests to vote on |
| `--headless` | `false` | Hide the browser window |

---

### `simulate` — Multi-user voting simulation

Simulate all configured users voting on existing tests.

```bash
tot-agent simulate
tot-agent simulate --votes-each 4
```

| Option | Default | Description |
|---|---|---|
| `--votes-each N` | `2` | Number of votes each user casts |
| `--headless` | `false` | Hide the browser window |

---

### `seed` — Full pipeline

Create tests, run voting simulation, and view results — all in one command.

```bash
tot-agent seed
tot-agent seed --tests 5 --vote-rounds 2
tot-agent seed --tests 3 --headless
```

| Option | Default | Description |
|---|---|---|
| `--tests N` | `5` | Number of A/B tests to create |
| `--vote-rounds N` | `1` | Voting rounds per user |
| `--headless` | `false` | Hide the browser window |

---

### `goal` — Custom natural-language goal

Execute any plain-English objective against the target site.

```bash
tot-agent goal "Log in as alice, navigate to /tests, and take a screenshot."
tot-agent goal "Create one test using two sci-fi covers, then have bob vote." --headless
```

!!! tip
    The `goal` command is the most flexible option.  Use it for one-off
    explorations or for goals that don't fit the pre-built commands.

---

### `users` — List simulated users

Print a table of all configured simulated users and their voting biases.

```bash
tot-agent users
```

Output:

```
┌──────────┬───────────┬──────────────┬────────────────────────┐
│ Username │ Password  │ Display Name │ Voting Bias            │
├──────────┼───────────┼──────────────┼────────────────────────┤
│ admin    │ admin123  │ Admin        │ random                 │
│ alice    │ password1 │ Alice        │ prefers_illustrated    │
│ bob      │ password2 │ Bob          │ prefers_dark           │
│ carol    │ password3 │ Carol        │ prefers_bright         │
│ dave     │ password4 │ Dave         │ random                 │
└──────────┴───────────┴──────────────┴────────────────────────┘
```

---

### `info` — Show configuration

Display current runtime configuration.

```bash
tot-agent info
tot-agent --model claude-sonnet-4-6 --site-url http://localhost:3000 info
```

---

### `covers` — Preview book covers

Fetch and display book covers without launching a browser.

```bash
tot-agent covers "mystery thriller" --count 5
tot-agent covers "fantasy epic" --count 3 --verify
```

| Option | Default | Description |
|---|---|---|
| `--count N` | `4` | Number of covers to fetch |
| `--verify` | `false` | HEAD-check each URL to confirm it resolves |

---

## Adapting to your application

`tot-agent` uses screenshots + vision so it adapts to most UIs, but you may
want to update `config.py` to match your application's routes:

| Setting | Purpose |
|---|---|
| `ROUTES["login"]` | Path to your login page |
| `ROUTES["create_test"]` | Path to the new-test form |
| `SIM_USERS` | Accounts that exist on your dev site |
| `SITE_URL` | Your dev server address |

---

## Running tests

```bash
# All unit tests (fast, no browser)
SKIP_INTEGRATION=1 pytest

# Unit + integration (requires Chromium)
pytest

# With coverage report
pytest --cov=src/tot_agent --cov-report=html:reports/coverage
open reports/coverage/index.html
```
