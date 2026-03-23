# Adding a New Platform

`tot-agent` ships with a built-in `THIS_OR_THAT` configuration for the
*this-or-that* application, but the scripted flow is fully platform-agnostic.
Pointing it at a different SaaS platform requires only a new `PlatformConfig`
dataclass instance — no Python logic needs to change.

This guide walks through every field, explains how to find the right values, and
shows a complete worked example.

---

## How the flow uses a PlatformConfig

The `ContestCreationFlow` in `src/tot_agent/flow.py` reads every route and CSS
selector from its `PlatformConfig` argument.  The flow itself is a fixed
sequence of steps:

```
switch_user → login → navigate to create form
  → fill title → fill description
  → fill image A label → fill image B label
  → upload cover A → upload cover B
  → fill tags → submit → verify redirect → logout
```

If a step fails (the result dict has `"ok": false`), the flow stops and returns
`False`.  No retry loop.  No LLM calls.

---

## PlatformConfig fields at a glance

```python
from dataclasses import dataclass

@dataclass
class PlatformConfig:
    name: str                         # display name for logs

    # Routes (site-relative paths)
    login_route: str                  # e.g. "/login"
    dashboard_route: str              # e.g. "/dashboard"
    create_route: str                 # e.g. "/contests/new"

    # Login form selectors
    email_selector: str               # e.g. "#email"
    password_selector: str            # e.g. "#password"
    login_submit_selector: str        # e.g. "button[type='submit']"
    login_success_fragment: str       # URL must contain this after login

    # Contest creation form selectors
    title_selector: str
    description_selector: str
    image_a_label_selector: str       # "" to skip
    image_b_label_selector: str       # "" to skip
    file_input_selector: str          # base selector for all file inputs
    image_a_file_nth: int             # 0-based index for cover-A file input
    image_b_file_nth: int             # 0-based index for cover-B file input
    tags_selector: str | None         # None if the form has no tag field
    submit_selector: str
    submit_success_excludes: str      # URL must NOT contain this after submit

    # Logout
    logout_selector: str | None       # click this to log out (preferred)
    logout_route: str | None          # navigate here if logout_selector is None
```

---

## Step-by-step: adding a platform

### 1. Identify the routes

Open the target app in your browser and note the URL for each page:

| Field | What to record |
|---|---|
| `login_route` | Path of the sign-in page, e.g. `/login` or `/auth/sign-in` |
| `dashboard_route` | Path you land on after login, e.g. `/dashboard` or `/home` |
| `create_route` | Path of the "create a contest / test" form |

### 2. Find the login form selectors

Open DevTools (`F12`) on the login page, click the **Elements** tab, and
inspect the email, password, and submit button.  Record their CSS selectors.

Common patterns:

```css
/* by id */
#email, #username, #user_email

/* by type + name */
input[type='email'][name='user[email]']

/* by aria-label */
input[aria-label='Email address']
```

Set `login_success_fragment` to a substring of the URL you land on after a
successful login (e.g. `"dashboard"`, `"home"`, `"app"`).  The flow checks
that this fragment is present after the submit redirect.

### 3. Find the contest-creation form selectors

Navigate to the create form and inspect each field.  Fill in:

- `title_selector` — the contest title input
- `description_selector` — the description textarea
- `image_a_label_selector` / `image_b_label_selector` — the edition name
  inputs.  If the form does not have label fields, set both to `""`.
- `tags_selector` — the tag/keyword input.  Set to `None` if absent.
- `submit_selector` — the form submit button.

#### File inputs

Inspect all `<input type="file">` elements on the page.  Count them in DOM
order (0-based) and record which index belongs to cover A and cover B.

```python
file_input_selector = "input[type='file']"
image_a_file_nth = 0   # first file input
image_b_file_nth = 1   # second file input
```

If the platform uses named inputs, you can be more specific:

```python
file_input_selector = "input[type='file'][name='coverImage']"
```

#### submit_success_excludes

After a successful submit, most platforms redirect away from the create page.
Set `submit_success_excludes` to a path fragment that will no longer be in the
URL on success.  For example, if the create URL is `/contests/new`, use
`"contests/new"`.  If the URL changes to `/contests/42`, the check passes.

### 4. Find the logout mechanism

Check whether the platform offers:

- A **link or button** to click (e.g. `a[href='/sign-out']`,
  `button[aria-label='Sign out']`, or the visible text `"Log out"`).
  Set this as `logout_selector`.
- A **route** to navigate to (e.g. `/logout`, `/auth/sign-out`).
  Set this as `logout_route` and leave `logout_selector = None`.

The flow tries `logout_selector` first.  If a logout action cannot be found,
both fields can be `None` — logout is logged as a warning but does not fail the
run.

### 5. Create the config instance

Add your config to `src/tot_agent/platform.py` alongside `THIS_OR_THAT`:

```python
# src/tot_agent/platform.py

BOOKDUEL_IO = PlatformConfig(
    name="bookduel-io",

    # Routes
    login_route="/auth/sign-in",
    dashboard_route="/app",
    create_route="/app/duels/new",

    # Login
    email_selector="input[name='email']",
    password_selector="input[name='password']",
    login_submit_selector="button[data-testid='login-btn']",
    login_success_fragment="/app",

    # Contest form
    title_selector="input[placeholder='Enter duel title']",
    description_selector="textarea[name='description']",
    image_a_label_selector="input[name='editionA']",
    image_b_label_selector="input[name='editionB']",
    file_input_selector="input[type='file']",
    image_a_file_nth=0,
    image_b_file_nth=1,
    tags_selector="input[aria-label='Tags']",
    submit_selector="button[type='submit']",
    submit_success_excludes="duels/new",

    # Logout
    logout_selector="a[href='/auth/sign-out']",
    logout_route=None,
)
```

### 6. Run the flow with your new config

Pass your config to `run_multi_user_flow()` or `ContestCreationFlow` directly:

```python
# In a script or custom CLI command:
import asyncio
from tot_agent.browser import BrowserManager
from tot_agent.flow import run_multi_user_flow
from tot_agent.platform import BOOKDUEL_IO

async def main():
    async with BrowserManager(headless=False) as bm:
        results = await run_multi_user_flow(bm, n_users=2, platform=BOOKDUEL_IO)
        for user, ok in results.items():
            print(user, "OK" if ok else "FAILED")

asyncio.run(main())
```

Or use the built-in CLI command (which defaults to `THIS_OR_THAT`) as a
template by copying the `contest` sub-command in `cli.py` and replacing
`THIS_OR_THAT` with your config.

---

## Troubleshooting selector failures

When a step fails, the log will show:

```
[Test1] Fill 'input[name="editionA"]' failed: {"ok": false, "error": "..."}
```

Use the `tot-agent covers` command to confirm book cover URLs resolve before
debugging browser steps:

```
tot-agent covers "fantasy epic" --count 2 --verify
```

To inspect the live form selectors interactively, open the browser
in non-headless mode (`--no-headless` is the default) and use DevTools.

---

## Advanced: overriding the research phase

The default research phase fetches a random cover pair from Open Library /
Google Books.  To use different data (e.g. a curated book list, a specific
edition comparison), subclass `ContestCreationFlow` and override
`_research_phase`:

```python
from tot_agent.flow import ContestCreationFlow, ContestData
from tot_agent.covers import download_cover_image

class CuratedContestFlow(ContestCreationFlow):
    def _research_phase(self) -> ContestData:
        cover_a_url = "https://covers.openlibrary.org/b/id/8739161-L.jpg"
        cover_b_url = "https://covers.openlibrary.org/b/id/8228374-L.jpg"
        return ContestData(
            title="Which Neuromancer cover do you prefer?",
            description="1984 Ace original vs 1994 anniversary edition.",
            image_a_label="1984 Ace Original",
            image_b_label="1994 Anniversary",
            image_a_path=download_cover_image(cover_a_url),
            image_b_path=download_cover_image(cover_b_url),
            tags="william gibson, cyberpunk, science fiction",
        )
```

The browser phase runs unchanged.

---

## Checklist

Before shipping a new platform config, verify:

- [ ] `tot-agent covers "<genre>" --verify` returns live cover URLs
- [ ] Login succeeds and `login_success_fragment` appears in the post-login URL
- [ ] The create form is reachable at `create_route` after login
- [ ] Each text field selector matches exactly one element
- [ ] File inputs are correctly addressed by `image_a_file_nth` / `image_b_file_nth`
- [ ] Submitting the form redirects to a URL that does not contain `submit_success_excludes`
- [ ] Logout works (or both logout fields are `None` and the warning is acceptable)
