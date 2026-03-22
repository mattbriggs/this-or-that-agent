# Setting Up Test Users

`tot-agent` logs into your site using a roster of simulated users defined in
[`src/tot_agent/config.py`](../src/tot_agent/config.py).  Each user has a
username, password, and a *voting bias* that shapes how the agent behaves when
casting votes.

---

## Default user roster

| Username | Password | Display name | Voting bias |
|---|---|---|---|
| `admin` | `admin123` | Admin | random |
| `alice` | `password1` | Alice | prefers_illustrated |
| `bob` | `password2` | Bob | prefers_dark |
| `carol` | `password3` | Carol | prefers_bright |
| `dave` | `password4` | Dave | random |

These accounts **must already exist on your target site** before running any
agent commands.  The agent navigates to `/login` and fills in the credentials
— it does not create the accounts itself.

---

## Creating the accounts on your dev site

Log in to your application as a super-user and create each account listed
above, or run whatever seed/fixture script your application provides.  For the
*This-or-That* platform the typical steps are:

```bash
# Start the dev server
cd /path/to/this-or-that
npm run dev

# Then open http://localhost:4321 in a browser and create each user
# through the admin panel, or use your app's CLI/seed command.
```

Once the accounts exist, run `tot-agent info` to confirm the agent can see the
correct `SITE_URL`, then try a quick smoke test:

```bash
tot-agent vote
```

---

## Customising the roster

Edit `SIM_USERS` in `src/tot_agent/config.py` to match the accounts on your
site:

```python
SIM_USERS: list[SimUser] = [
    SimUser("admin",   "mypassword",  "Admin", voting_bias="random"),
    SimUser("tester1", "pass1",       "Tester 1", voting_bias="prefers_dark"),
]
```

### Voting bias options

| Value | Behaviour |
|---|---|
| `random` | Picks covers without any preference |
| `prefers_dark` | Tends to favour darker cover designs |
| `prefers_bright` | Tends to favour brighter cover designs |
| `prefers_illustrated` | Tends to favour illustrated / artwork covers |

---

## Listing configured users

```bash
tot-agent users
```

This prints the current `SIM_USERS` roster so you can confirm the agent is
using the accounts you expect.

---

## Security note

The default credentials (`admin123`, `password1`, …) are intentionally weak
and intended **only for local development**.  Never use these accounts or
passwords on a staging or production environment.
