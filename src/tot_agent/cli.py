"""
cli.py — Full-featured command-line interface for the tot-agent tool.

Entry point: ``tot-agent`` (registered via ``pyproject.toml`` ``[project.scripts]``).

Global options (available on every sub-command via the top-level group):

``--log-level``
    Python logging level: ``DEBUG``, ``INFO`` (default), ``WARNING``, ``ERROR``.
``--log-file``
    Path to write log output in addition to stderr.
``--model``
    Override the Claude model (e.g. ``claude-opus-4-5``).
``--max-steps``
    Override the per-run step ceiling.
``--site-url``
    Override the target application base URL.
``--headless``
    Run the browser without a visible window (inheritable by sub-commands).

Sub-commands
------------
``create``   Create A/B tests with real book covers.
``vote``     Have a single simulated user cast votes.
``simulate`` Simulate all configured users voting.
``seed``     Full pipeline: create tests, simulate voting, view results.
``goal``     Execute a custom natural-language goal.
``users``    List configured simulated users.
``info``     Show current runtime configuration.
``covers``   Preview book covers from a search query (no browser needed).
"""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from tot_agent import __version__

console = Console()
logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _configure_logging(level: str, log_file: str | None) -> None:
    """Configure the root logger with the requested level and optional file handler.

    :param str level: Logging level name (``"DEBUG"``, ``"INFO"``, etc.).
    :param str or None log_file: Optional file path to also write logs to.
    """
    numeric = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=handlers,
    )
    logger.debug("Logging configured: level=%s, file=%s", level, log_file)


# ---------------------------------------------------------------------------
# Shared async runner
# ---------------------------------------------------------------------------


def _run_agent(
    goal: str,
    headless: bool,
    model: str | None,
    max_steps: int | None,
    site_url: str | None,
) -> None:
    """Instantiate and run the agent for *goal*.

    :param str goal: Plain-English objective.
    :param bool headless: Whether to hide the browser window.
    :param str or None model: Optional model override.
    :param int or None max_steps: Optional max-steps override.
    :param str or None site_url: Optional site URL override.
    """
    import tot_agent.config as _cfg
    from tot_agent.agent import BrowserAgent, ConsoleObserver, LoggingObserver
    from tot_agent.browser import BrowserManager

    # Apply overrides before constructing the agent.
    effective_model = model or _cfg.AGENT_MODEL
    effective_steps = max_steps or _cfg.MAX_AGENT_STEPS
    effective_url = site_url or _cfg.SITE_URL

    async def _run() -> None:
        async with BrowserManager(headless=headless, site_url=effective_url) as bm:
            agent = BrowserAgent(
                bm,
                observers=[ConsoleObserver(), LoggingObserver()],
                model=effective_model,
                max_steps=effective_steps,
            )
            await agent.run(goal)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(__version__, prog_name="tot-agent")
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Python logging level.",
    envvar="TOT_LOG_LEVEL",
)
@click.option(
    "--log-file",
    default=None,
    metavar="PATH",
    help="Write logs to this file in addition to stderr.",
    envvar="TOT_LOG_FILE",
)
@click.option("--model", default=None, metavar="MODEL", help="Override Claude model ID.",
              envvar="AGENT_MODEL")
@click.option("--max-steps", default=None, type=int, metavar="N",
              help="Override per-run step ceiling.", envvar="MAX_AGENT_STEPS")
@click.option("--site-url", default=None, metavar="URL",
              help="Override target application base URL.", envvar="SITE_URL")
@click.pass_context
def cli(
    ctx: click.Context,
    log_level: str,
    log_file: str | None,
    model: str | None,
    max_steps: int | None,
    site_url: str | None,
) -> None:
    """tot-agent — Autonomous browser agent for scripted GUI testing.

    Drive a real Playwright browser with Claude vision + tool-use to execute
    natural-language test goals against any web application.
    """
    _configure_logging(log_level, log_file)
    ctx.ensure_object(dict)
    ctx.obj["model"] = model
    ctx.obj["max_steps"] = max_steps
    ctx.obj["site_url"] = site_url


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--count", default=5, show_default=True, help="Number of A/B tests to create.")
@click.option("--genre", default="mixed", show_default=True,
              help="Book genre ('mixed' for random variety).")
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def create(ctx: click.Context, count: int, genre: str, headless: bool) -> None:
    """Create A/B tests with real book covers fetched from Open Library."""
    from tot_agent.agent import CreateTestsGoal
    goal = CreateTestsGoal(count=count, genre=genre).build()
    _run_agent(goal, headless, ctx.obj["model"], ctx.obj["max_steps"], ctx.obj["site_url"])


@cli.command()
@click.option("--user", required=True, help="Username of the simulated voter.")
@click.option("--count", default=3, show_default=True, help="Number of tests to vote on.")
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def vote(ctx: click.Context, user: str, count: int, headless: bool) -> None:
    """Have a single simulated user cast votes on existing A/B tests."""
    from tot_agent.agent import VoteGoal
    from tot_agent.config import get_user

    u = get_user(user)
    if u is None:
        from tot_agent.config import SIM_USERS

        available = [x.username for x in SIM_USERS]
        raise click.BadParameter(
            f"Unknown user {user!r}. Available: {available}", param_hint="--user"
        )
    goal = VoteGoal(u.username, u.password, vote_count=count, bias=u.voting_bias).build()
    _run_agent(goal, headless, ctx.obj["model"], ctx.obj["max_steps"], ctx.obj["site_url"])


@cli.command()
@click.option("--votes-each", default=2, show_default=True,
              help="Number of votes each user casts.")
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def simulate(ctx: click.Context, votes_each: int, headless: bool) -> None:
    """Simulate all configured users voting on existing A/B tests."""
    from tot_agent.agent import SimulateAllUsersGoal
    goal = SimulateAllUsersGoal(vote_count_each=votes_each).build()
    _run_agent(goal, headless, ctx.obj["model"], ctx.obj["max_steps"], ctx.obj["site_url"])


@cli.command()
@click.option("--tests", default=5, show_default=True, help="Number of A/B tests to seed.")
@click.option("--vote-rounds", default=1, show_default=True,
              help="Voting rounds per user.")
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def seed(ctx: click.Context, tests: int, vote_rounds: int, headless: bool) -> None:
    """Full pipeline: create tests, simulate all users voting, view results."""
    from tot_agent.agent import FullSeedGoal
    goal = FullSeedGoal(test_count=tests, vote_rounds=vote_rounds).build()
    _run_agent(goal, headless, ctx.obj["model"], ctx.obj["max_steps"], ctx.obj["site_url"])


@cli.command()
@click.argument("goal_text")
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def goal(ctx: click.Context, goal_text: str, headless: bool) -> None:
    """Execute a custom natural-language GOAL_TEXT against the target site."""
    _run_agent(goal_text, headless, ctx.obj["model"], ctx.obj["max_steps"], ctx.obj["site_url"])


@cli.command()
@click.option(
    "--users", "n_users",
    default=1,
    show_default=True,
    help="Number of randomly chosen users to run the flow for.",
)
@click.option("--headless", is_flag=True, help="Run browser without visible window.")
@click.pass_context
def contest(ctx: click.Context, n_users: int, headless: bool) -> None:
    """Create contests via the scripted direct flow (no agentic loop).

    Randomly selects N users from the configured roster, fetches a fresh book
    cover pair for each, and submits the contest-creation form step-by-step
    using Playwright.  Each run ends with a logout before the next user begins.

    To target a different platform, pass a custom PlatformConfig to
    run_multi_user_flow() in your own script.  See docs/adding-a-platform.md.
    """
    import asyncio

    import tot_agent.config as _cfg
    from tot_agent.browser import BrowserManager
    from tot_agent.flow import run_multi_user_flow
    from tot_agent.platform import THIS_OR_THAT

    effective_url = ctx.obj["site_url"] or _cfg.SITE_URL

    async def _run() -> None:
        async with BrowserManager(headless=headless, site_url=effective_url) as bm:
            results = await run_multi_user_flow(
                bm, n_users=n_users, platform=THIS_OR_THAT
            )
        table = Table(
            title="Contest Creation Results",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("User")
        table.add_column("Result")
        for username, ok in results.items():
            status = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
            table.add_row(username, status)
        console.print(table)

    asyncio.run(_run())


@cli.command()
def users() -> None:
    """List all configured simulated users."""
    from tot_agent.config import SIM_USERS
    table = Table(title="Simulated Users", show_header=True, header_style="bold cyan")
    table.add_column("Username", style="cyan")
    table.add_column("Password")
    table.add_column("Display Name")
    table.add_column("Voting Bias")
    for u in SIM_USERS:
        table.add_row(u.username, u.password, u.display_name, u.voting_bias)
    console.print(table)


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show current runtime configuration (env vars and active overrides)."""
    import tot_agent.config as _cfg

    table = Table(title="Runtime Configuration", show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value")
    rows = [
        ("site_url", ctx.obj.get("site_url") or _cfg.SITE_URL),
        ("model", ctx.obj.get("model") or _cfg.AGENT_MODEL),
        ("max_steps", str(ctx.obj.get("max_steps") or _cfg.MAX_AGENT_STEPS)),
        ("api_key_set", "yes" if _cfg.ANTHROPIC_API_KEY else "[red]NO[/red]"),
        ("screenshot_size", f"{_cfg.SCREENSHOT_WIDTH}x{_cfg.SCREENSHOT_HEIGHT}"),
        ("navigation_timeout_ms", str(_cfg.NAVIGATION_TIMEOUT_MS)),
        ("action_timeout_ms", str(_cfg.ACTION_TIMEOUT_MS)),
        ("wait_for_element_timeout_ms", str(_cfg.WAIT_FOR_ELEMENT_TIMEOUT_MS)),
        ("page_ready_timeout_ms", str(_cfg.PAGE_READY_TIMEOUT_MS)),
        ("sim_users", str(len(_cfg.SIM_USERS))),
    ]
    for name, val in rows:
        table.add_row(name, val)
    console.print(table)
    console.print()
    console.print("[dim]Routes:[/dim]")
    for route, path in _cfg.ROUTES.items():
        console.print(f"  [cyan]{route}[/cyan] -> {path}")


@cli.command()
@click.argument("query")
@click.option("--count", default=4, show_default=True,
              help="Number of covers to fetch.")
@click.option("--verify", is_flag=True,
              help="HEAD-check each URL to confirm it resolves.")
def covers(query: str, count: int, verify: bool) -> None:
    """Preview book covers from QUERY without launching a browser.

    Example:

        tot-agent covers "fantasy epic" --count 3 --verify
    """
    from tot_agent.covers import CoverFetcher, verify_cover_url

    fetcher = CoverFetcher()
    results = fetcher.fetch(query, count=count)
    if not results:
        console.print(f"[red]No covers found for {query!r}[/red]")
        return
    table = Table(title=f"Covers: {query!r}", show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title")
    table.add_column("Author")
    table.add_column("Source")
    table.add_column("URL")
    if verify:
        table.add_column("Live?")
    for i, c in enumerate(results, 1):
        row = [str(i), c.title, c.author, c.source, c.cover_url]
        if verify:
            ok = verify_cover_url(c.cover_url)
            row.append("[green]yes[/green]" if ok else "[red]no[/red]")
        table.add_row(*row)
    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
