"""
config.py — Configuration dataclasses, environment loading, and tuning knobs.

All runtime configuration is resolved once at import time from environment
variables (via :mod:`dotenv`) with sensible defaults so the package works
out-of-the-box for a standard local development setup.

Environment variables
---------------------
``ANTHROPIC_API_KEY``
    Required.  Your Anthropic API key.
``SITE_URL``
    Base URL of the target web application.  Defaults to
    ``http://localhost:4321``.
``AGENT_MODEL``
    Claude model identifier.  Defaults to ``claude-opus-4-5``.
``MAX_AGENT_STEPS``
    Hard ceiling on tool-call iterations per agent run.  Defaults to ``40``.
``NAVIGATION_TIMEOUT_MS``
    Timeout for page navigation and route transitions.
``ACTION_TIMEOUT_MS``
    Timeout for click/fill/select interactions.
``WAIT_FOR_ELEMENT_TIMEOUT_MS``
    Timeout for explicit selector waits.
``PAGE_READY_TIMEOUT_MS``
    Best-effort timeout for waiting on a new DOM-ready state after an action.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

SITE_URL: str = os.getenv("SITE_URL", "http://localhost:4321")
"""Base URL of the target application (e.g. ``http://localhost:4321``)."""

ROUTES: dict[str, str] = {
    "login": "/login",
    "tests": "/tests",
    "create_test": "/tests/new",
    "dashboard": "/",
    "logout": "/logout",
}
"""Relative route paths.  Override in a subclass or at runtime to match your
application's URL structure."""


# ---------------------------------------------------------------------------
# Anthropic / agent tuning
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
"""Anthropic API key.  Loaded from the ``ANTHROPIC_API_KEY`` environment
variable.  Raises :class:`RuntimeError` at agent construction time if unset."""

AGENT_MODEL: str = os.getenv("AGENT_MODEL", "claude-opus-4-5")
"""Claude model ID used for the agentic loop."""

MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "40"))
"""Maximum number of tool-call iterations before the agent gives up."""

SCREENSHOT_WIDTH: int = 1280
"""Browser viewport width in pixels."""

SCREENSHOT_HEIGHT: int = 900
"""Browser viewport height in pixels."""

NAVIGATION_TIMEOUT_MS: int = int(os.getenv("NAVIGATION_TIMEOUT_MS", "15000"))
"""Navigation timeout in milliseconds."""

ACTION_TIMEOUT_MS: int = int(os.getenv("ACTION_TIMEOUT_MS", "5000"))
"""Default timeout for click/fill/select interactions in milliseconds."""

WAIT_FOR_ELEMENT_TIMEOUT_MS: int = int(os.getenv("WAIT_FOR_ELEMENT_TIMEOUT_MS", "8000"))
"""Default timeout for explicit selector waits in milliseconds."""

PAGE_READY_TIMEOUT_MS: int = int(os.getenv("PAGE_READY_TIMEOUT_MS", "4000"))
"""Best-effort wait time for DOM readiness after a form submission or click."""


# ---------------------------------------------------------------------------
# Simulated users
# ---------------------------------------------------------------------------


@dataclass
class SimUser:
    """A simulated user account used during automated testing.

    :param str username: Login username.
    :param str password: Login password.
    :param str display_name: Human-readable name shown in logs.  Defaults to
        *username* when blank.
    :param str voting_bias: Personality hint fed to the agent when casting votes.
        One of ``"random"``, ``"prefers_dark"``, ``"prefers_bright"``, or
        ``"prefers_illustrated"``.
    """

    username: str
    password: str
    display_name: str = ""
    voting_bias: str = "random"

    def __post_init__(self) -> None:
        """Ensure *display_name* falls back to *username* when left blank."""
        if not self.display_name:
            self.display_name = self.username
        logger.debug("SimUser created: %s (bias=%s)", self.username, self.voting_bias)

    def __repr__(self) -> str:
        return (
            f"SimUser(username={self.username!r}, display_name={self.display_name!r}, "
            f"voting_bias={self.voting_bias!r})"
        )


SIM_USERS: list[SimUser] = [
    SimUser("test1@finalstatepress.com", "testuser1970", "Test1", voting_bias="random"),
    SimUser("test2@finalstatepress.com", "test2user1970", "Test2", voting_bias="prefers_illustrated"),
    SimUser("test3@finalstatepress.com", "test3user1970", "Test3", voting_bias="prefers_dark"),
    SimUser("test4@finalstatepress.com", "test4user1970", "Test4", voting_bias="prefers_bright"),
    SimUser("test5@finalstatepress.com", "test5user1970", "Test5", voting_bias="random"),
]
"""Default roster of simulated users.  Edit this list to match the accounts
that exist (or that you will create) on your dev site."""


def get_user(username: str) -> SimUser | None:
    """Look up a :class:`SimUser` by username.

    :param str username: The username to search for.
    :returns: The matching :class:`SimUser`, or ``None`` if not found.
    :rtype: SimUser or None
    """
    for user in SIM_USERS:
        if user.username == username:
            return user
    logger.warning("User %r not found in SIM_USERS", username)
    return None


# ---------------------------------------------------------------------------
# Open Library / Google Books
# ---------------------------------------------------------------------------

OPEN_LIBRARY_SEARCH_URL: str = "https://openlibrary.org/search.json"
"""Open Library JSON search endpoint."""

OPEN_LIBRARY_COVER_URL: str = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
"""Template URL for Open Library cover images."""

GOOGLE_BOOKS_URL: str = "https://www.googleapis.com/books/v1/volumes"
"""Google Books API volumes endpoint (no key required for low-volume search)."""

COVER_SEARCH_QUERIES: list[str] = [
    "science fiction novel",
    "fantasy epic",
    "literary fiction",
    "mystery thriller",
    "horror",
    "romance",
    "historical fiction",
    "biography",
]
"""Genre queries cycled when seeding test data with random book covers."""
