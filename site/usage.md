# Usage Guide

All commands are available through the `tot-agent` entry point installed by
`pip install -e .`.

---

## Choosing a mode

`tot-agent` has two execution modes.  Pick the one that fits the task:

| Task | Mode | Command |
|---|---|---|
| Create contests with real covers | Scripted (no LLM) | `contest` |
| Create A/B tests via agent | Agentic | `create` |
| Simulate user voting | Agentic | `vote` / `simulate` |
| Full seed pipeline | Agentic | `seed` |
| One-off custom goal | Agentic | `goal` |

Use **scripted mode** (`contest`) for production seeding — it is deterministic,
never loops, and costs no API tokens.  Use **agentic mode** for exploratory
testing or goals that cannot be fully specified in advance.

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
| `--model MODEL` | `claude-opus-4-5` | Override Claude model ID (agentic commands only) |
| `--max-steps N` | `40` | Override per-run iteration ceiling (agentic commands only) |
| `--site-url URL` | `http://localhost:4321` | Override target application base URL |

```bash
# Enable debug logging and write to a file
tot-agent --log-level DEBUG --log-file run.log seed --tests 3
```

---

## Scripted commands

### `contest` — Create contests (scripted, no LLM)

Randomly selects users from the configured roster, fetches a fresh book cover
pair for each, and submits the contest-creation form step-by-step using
Playwright.  Each run ends with a logout before the next user begins.

```bash
tot-agent contest
tot-agent contest --users 3
tot-agent contest --users 5 --headless
```

| Option | Default | Description |
|---|---|---|
| `--users N` | `1` | Number of randomly chosen users to run the flow for |
| `--headless` | `false` | Hide the browser window |

**What it does per user:**

1. Fetches a random book cover pair from Open Library / Google Books (no LLM)
2. Downloads both cover images to temporary local files
3. Logs in using that user's credentials
4. Navigates to the contest-creation form
5. Fills each field — title, description, image labels, tags
6. Uploads both cover images
7. Submits the form and confirms the redirect
8. Logs out

Results are printed as a summary table:

```
┌────────────────────────────────┬────────┐
│ User                           │ Result │
├────────────────────────────────┼────────┤
│ test1@finalstatepress.com      │ OK     │
│ test3@finalstatepress.com      │ FAILED │
└────────────────────────────────┴────────┘
```

!!! tip "Targeting a different platform"
    By default `contest` targets the *This-or-That* platform using the
    `THIS_OR_THAT` config.  To point it at a different SaaS, create a
    `PlatformConfig` for that site and pass it to `run_multi_user_flow()`
    in a custom script.  See [Adding a Platform](../adding-a-platform.md).

---

## Agentic commands

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
tot-agent vote --user test1@finalstatepress.com --count 3
tot-agent vote --user test2@finalstatepress.com --count 5 --headless
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
tot-agent goal "Log in as test1, navigate to /contests, and take a screenshot."
tot-agent goal "Create one test using two sci-fi covers, then have test2 vote." --headless
```

!!! tip
    The `goal` command is the most flexible option.  Use it for one-off
    explorations or for goals that don't fit the pre-built commands.

---

## Utility commands

### `users` — List simulated users

Print a table of all configured simulated users and their voting biases.

```bash
tot-agent users
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

Fetch and display book covers without launching a browser.  Useful for
verifying cover sources are reachable before running a full flow.

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

### Scripted mode — use PlatformConfig

The `contest` command reads every route and CSS selector from a `PlatformConfig`
instance in `src/tot_agent/platform.py`.  To target a new SaaS platform:

1. Inspect the login and contest-creation pages with browser DevTools
2. Add a new `PlatformConfig` instance to `platform.py`
3. Pass it to `run_multi_user_flow()` in a custom script

No other code needs to change.  See [Adding a Platform](../adding-a-platform.md)
for a complete step-by-step guide.

### Agentic mode — update `config.py`

The agentic commands use vision to discover the UI, but they still reference
route paths from `config.py`:

| Setting | Purpose |
|---|---|
| `ROUTES["login"]` | Path to your login page |
| `ROUTES["create_test"]` | Path to the new-test form |
| `SIM_USERS` | Accounts that exist on your dev site |
| `SITE_URL` | Your dev server address |

---

## Running tests

```bash
# Unit tests only (fast, no browser or network)
SKIP_INTEGRATION=1 pytest

# Unit + integration (requires Chromium and internet access)
pytest

# With HTML coverage report
pytest --cov=src/tot_agent --cov-report=html:reports/coverage
open reports/coverage/index.html
```
