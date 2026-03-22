# Installation

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.12 | Uses `match` statements and modern type hints |
| pip | 23+ | Required for PEP 517 installs |
| Playwright / Chromium | 1.44 | Installed separately (see below) |
| Anthropic API key | — | Required for Claude vision |

---

## Virtual environment setup

It is strongly recommended to install `tot-agent` in an isolated virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

---

## Install from source

```bash
git clone https://github.com/mattbriggs/this-or-that-agent
cd this-or-that-agent

# Core dependencies only
pip install -e .

# Core + development dependencies (tests, docs)
pip install -e ".[dev]"
```

---

## Install Playwright browsers

Playwright downloads browser binaries separately from the Python package.
Only Chromium is required by tot-agent.

```bash
playwright install chromium
```

!!! tip
    Run `playwright install --help` to see options for installing in a custom
    location or behind a proxy.

---

## Configure environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional overrides (shown with defaults)
SITE_URL=http://localhost:4321
AGENT_MODEL=claude-opus-4-5
MAX_AGENT_STEPS=40
```

---

## Verify the install

```bash
tot-agent --version
tot-agent info
```

The `info` command prints the active configuration — useful for confirming
that your API key and site URL are loaded correctly.

---

## Target application

`tot-agent` is designed for local development servers.  Start your target
application before running any agent commands.  For the *This-or-That*
platform:

```bash
cd /path/to/this-or-that
npm run dev           # Starts at http://localhost:4321 by default
```

Then in a separate terminal:

```bash
tot-agent seed --tests 3
```
