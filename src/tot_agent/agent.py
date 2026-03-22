"""
agent.py — Core agentic loop and goal template builders.

Architecture — Observer pattern
--------------------------------
The agent emits :class:`AgentEvent` objects at each significant step of its
execution.  Any number of :class:`AgentObserver` instances can be attached to
receive these events.  Two concrete observers are bundled:

* :class:`ConsoleObserver` — renders events to the terminal via :mod:`rich`.
* :class:`LoggingObserver` — writes events to the standard :mod:`logging`
  hierarchy (useful for CI/CD pipelines and file-based audit trails).

This separation means the core loop never directly calls ``print`` or
``console.print``.

Usage::

    from tot_agent.browser import BrowserManager
    from tot_agent.agent import BrowserAgent, ConsoleObserver, LoggingObserver

    async with BrowserManager() as bm:
        agent = BrowserAgent(bm, observers=[ConsoleObserver(), LoggingObserver()])
        summary = await agent.run("Log in as admin and take a screenshot.")
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

import anthropic
from rich.console import Console
from rich.panel import Panel

from tot_agent.config import (
    AGENT_MODEL,
    ANTHROPIC_API_KEY,
    MAX_AGENT_STEPS,
    SIM_USERS,
    SimUser,
)
from tot_agent.browser import BrowserManager
from tot_agent.tools import TOOL_DEFINITIONS, dispatch, format_tool_result

logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Observer pattern — events
# ---------------------------------------------------------------------------


class EventType(Enum):
    """Enumeration of agent lifecycle events."""

    GOAL_START = auto()
    """The agent has received a new goal and is about to start the loop."""
    STEP_START = auto()
    """A new iteration of the tool-call loop is beginning."""
    AGENT_TEXT = auto()
    """The model produced a text block (reasoning or narration)."""
    TOOL_CALL = auto()
    """The model requested a tool execution."""
    TOOL_RESULT = auto()
    """A tool call completed and returned a result."""
    GOAL_COMPLETE = auto()
    """The agent finished successfully (``stop_reason == "end_turn"``)."""
    STEP_LIMIT = auto()
    """The loop was terminated because :data:`~tot_agent.config.MAX_AGENT_STEPS`
    was reached."""


@dataclass
class AgentEvent:
    """Carries data from the agent loop to registered observers.

    :param event_type: The kind of event that occurred.
    :type event_type: EventType
    :param data: Arbitrary key-value payload; keys vary per event type.
    :type data: dict[str, Any]
    """

    event_type: EventType
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Observer pattern — abstract observer
# ---------------------------------------------------------------------------


class AgentObserver(ABC):
    """Abstract base class for agent event observers (Observer pattern).

    Subclass this and implement :meth:`on_event` to react to agent lifecycle
    events without modifying the agent core.
    """

    @abstractmethod
    def on_event(self, event: AgentEvent) -> None:
        """Handle an agent event.

        :param event: The event to handle.
        :type event: AgentEvent
        """


# ---------------------------------------------------------------------------
# Concrete observers
# ---------------------------------------------------------------------------


class ConsoleObserver(AgentObserver):
    """Renders agent events to the terminal using :class:`rich.console.Console`.

    :param console: Rich console instance.  A new one is created if omitted.
    :type console: rich.console.Console or None
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        self._console = console or Console()

    def on_event(self, event: AgentEvent) -> None:  # noqa: C901
        """Render *event* to the terminal.

        :param event: Agent event to render.
        :type event: AgentEvent
        """
        match event.event_type:
            case EventType.GOAL_START:
                self._console.print(
                    Panel(
                        f"[bold]Goal:[/bold] {event.data.get('goal', '')}",
                        title="Agent",
                        border_style="blue",
                    )
                )
            case EventType.STEP_START:
                step = event.data.get("step", "?")
                self._console.print(
                    f"\n[dim]-- Step {step} ------------------------------------------[/dim]"
                )
            case EventType.AGENT_TEXT:
                text = event.data.get("text", "")
                if text.strip():
                    self._console.print(f"[bold cyan]Agent:[/bold cyan] {text}")
            case EventType.TOOL_CALL:
                name = event.data.get("name", "")
                inp = event.data.get("input", {})
                preview = json.dumps(inp, ensure_ascii=False)[:120]
                self._console.print(
                    f"  [yellow]-> tool:[/yellow] [bold]{name}[/bold] [dim]{preview}[/dim]"
                )
            case EventType.TOOL_RESULT:
                is_screenshot = event.data.get("is_screenshot", False)
                if is_screenshot:
                    self._console.print("  [green]screenshot captured[/green]")
                else:
                    preview = str(event.data.get("result", ""))[:200]
                    self._console.print(f"  [green]✓[/green] {preview}")
            case EventType.GOAL_COMPLETE:
                summary = event.data.get("summary", "Goal completed.")
                self._console.print(
                    Panel(summary, title="Done", border_style="green")
                )
            case EventType.STEP_LIMIT:
                self._console.print(
                    Panel(
                        event.data.get("message", "Step limit reached."),
                        title="Step limit",
                        border_style="yellow",
                    )
                )


class LoggingObserver(AgentObserver):
    """Writes agent events to the Python :mod:`logging` hierarchy.

    :param log: Logger to write to.  Defaults to this module's logger.
    :type log: logging.Logger or None
    """

    def __init__(self, log: Optional[logging.Logger] = None) -> None:
        self._log = log or logger

    def on_event(self, event: AgentEvent) -> None:
        """Log *event* at an appropriate level.

        :param event: Agent event to log.
        :type event: AgentEvent
        """
        match event.event_type:
            case EventType.GOAL_START:
                self._log.info("Goal start: %s", event.data.get("goal", ""))
            case EventType.STEP_START:
                self._log.debug("Step %s start", event.data.get("step"))
            case EventType.AGENT_TEXT:
                self._log.debug("Agent text: %s", event.data.get("text", "")[:200])
            case EventType.TOOL_CALL:
                self._log.debug(
                    "Tool call: %s %s",
                    event.data.get("name"),
                    event.data.get("input"),
                )
            case EventType.TOOL_RESULT:
                self._log.debug(
                    "Tool result (screenshot=%s): %s",
                    event.data.get("is_screenshot"),
                    str(event.data.get("result", ""))[:200],
                )
            case EventType.GOAL_COMPLETE:
                self._log.info("Goal complete: %s", event.data.get("summary", ""))
            case EventType.STEP_LIMIT:
                self._log.warning("Step limit reached: %s", event.data.get("message"))


# ---------------------------------------------------------------------------
# System prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are an autonomous browser agent testing a web application.

Your capabilities:
- Take screenshots to see the current UI state
- Navigate, click, fill forms in a real browser
- Switch between multiple simulated user accounts (each with its own session)
- Fetch real book cover images from Open Library / Google Books
- Create A/B tests, cast votes, and simulate user behaviour

Available simulated users:
{users}

Key principles:
1. ALWAYS take a screenshot after navigation or form submission to verify the result.
2. If a UI element is not where you expect, take a screenshot and re-examine.
3. When creating A/B tests, use real book cover URLs from fetch_book_covers.
4. When voting, pick the cover that fits the user's voting_bias (random = pick either).
5. After completing a goal, give a concise summary of what was accomplished.
6. Be resilient -- if a click or fill fails, screenshot the page and try an alternative.
7. Login state is per-user-context. After switch_user you may need to login again if
   that user has not authenticated in this session.

The site is a local web application. Routes may vary -- use screenshots
to discover the actual UI rather than assuming fixed selectors.
"""


def _build_system_prompt(users: list[SimUser]) -> str:
    """Render the system prompt with the simulated user roster.

    :param users: List of :class:`~tot_agent.config.SimUser` objects.
    :type users: list[SimUser]
    :returns: Fully rendered system prompt string.
    :rtype: str
    """
    user_lines = "\n".join(
        f"  - {u.username} / {u.password} (bias: {u.voting_bias})" for u in users
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(users=user_lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class BrowserAgent:
    """Vision-capable agentic loop that drives a Playwright browser.

    The agent calls Claude with :data:`~tot_agent.tools.TOOL_DEFINITIONS` and
    iterates until the model reaches ``end_turn`` or the step cap is hit.

    :param bm: An initialised :class:`~tot_agent.browser.BrowserManager`.
    :type bm: BrowserManager
    :param observers: Observers to notify at each lifecycle event.  Defaults
        to ``[ConsoleObserver(), LoggingObserver()]``.
    :type observers: list[AgentObserver] or None
    :param model: Claude model identifier.  Defaults to
        :data:`~tot_agent.config.AGENT_MODEL`.
    :type model: str
    :param max_steps: Maximum tool-call iterations per goal.  Defaults to
        :data:`~tot_agent.config.MAX_AGENT_STEPS`.
    :type max_steps: int
    :param api_key: Anthropic API key.  Defaults to
        :data:`~tot_agent.config.ANTHROPIC_API_KEY`.
    :type api_key: str or None
    :raises RuntimeError: At construction time if *api_key* is ``None``.
    """

    def __init__(
        self,
        bm: BrowserManager,
        observers: Optional[list[AgentObserver]] = None,
        model: str = AGENT_MODEL,
        max_steps: int = MAX_AGENT_STEPS,
        api_key: Optional[str] = ANTHROPIC_API_KEY,
    ) -> None:
        if api_key is None:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it as an environment variable or add it to .env."
            )
        self.bm = bm
        self.model = model
        self.max_steps = max_steps
        self._observers: list[AgentObserver] = observers or [
            ConsoleObserver(),
            LoggingObserver(),
        ]
        self._client = anthropic.Anthropic(api_key=api_key)
        self._system = _build_system_prompt(SIM_USERS)

    # ------------------------------------------------------------------
    # Observer management
    # ------------------------------------------------------------------

    def add_observer(self, observer: AgentObserver) -> None:
        """Register an additional observer.

        :param observer: Observer to add.
        :type observer: AgentObserver
        """
        self._observers.append(observer)

    def remove_observer(self, observer: AgentObserver) -> None:
        """Deregister an observer.

        :param observer: Observer to remove.
        :type observer: AgentObserver
        """
        self._observers.remove(observer)

    def _emit(self, event: AgentEvent) -> None:
        """Notify all registered observers of *event*.

        :param event: The event to broadcast.
        :type event: AgentEvent
        """
        for obs in self._observers:
            obs.on_event(event)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def run(self, goal: str) -> str:
        """Execute the agent loop until the goal is achieved or the step cap is hit.

        :param goal: Plain-English objective for the agent.
        :type goal: str
        :returns: A human-readable summary of what was accomplished.
        :rtype: str
        """
        self._emit(AgentEvent(EventType.GOAL_START, {"goal": goal}))
        logger.info("Agent run started: %s", goal[:80])

        messages: list[dict] = [{"role": "user", "content": goal}]

        for step in range(1, self.max_steps + 1):
            self._emit(AgentEvent(EventType.STEP_START, {"step": step}))

            response = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self._system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            text_parts: list[str] = []
            tool_calls: list[Any] = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    self._emit(
                        AgentEvent(EventType.AGENT_TEXT, {"text": block.text})
                    )
                elif block.type == "tool_use":
                    tool_calls.append(block)

            # Append the full assistant response to history.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_calls:
                summary = "\n".join(text_parts) or "Goal completed."
                self._emit(
                    AgentEvent(EventType.GOAL_COMPLETE, {"summary": summary})
                )
                logger.info("Agent completed in %d step(s)", step)
                return summary

            # Execute tool calls.
            tool_results: list[dict] = []
            for tc in tool_calls:
                self._emit(
                    AgentEvent(
                        EventType.TOOL_CALL,
                        {"name": tc.name, "input": tc.input},
                    )
                )
                result = await dispatch(tc.name, tc.input, self.bm)
                is_screenshot = isinstance(result, dict) and result.get("type") == "screenshot"
                self._emit(
                    AgentEvent(
                        EventType.TOOL_RESULT,
                        {"result": result, "is_screenshot": is_screenshot},
                    )
                )
                tool_results.append(format_tool_result(tc.id, result))

            messages.append({"role": "user", "content": tool_results})

        msg = f"Reached step limit ({self.max_steps}). Last goal: {goal}"
        self._emit(AgentEvent(EventType.STEP_LIMIT, {"message": msg}))
        logger.warning("Step limit reached after %d steps", self.max_steps)
        return msg


# ---------------------------------------------------------------------------
# Goal template builders (Template Method pattern)
# ---------------------------------------------------------------------------


class GoalTemplate:
    """Base class for structured goal strings (Template Method pattern).

    Subclass and override :meth:`build` to create reusable, parameterised
    goal strings for common test scenarios.
    """

    def build(self, **kwargs: Any) -> str:
        """Render the goal string from the provided keyword arguments.

        :returns: A plain-English goal string ready to pass to
            :meth:`BrowserAgent.run`.
        :rtype: str
        :raises NotImplementedError: In the base class.
        """
        raise NotImplementedError


class CreateTestsGoal(GoalTemplate):
    """Goal: create A/B tests with real book covers.

    :param count: Number of tests to create.  Defaults to ``5``.
    :type count: int
    :param genre: Book genre, or ``"mixed"`` for variety.  Defaults to
        ``"mixed"``.
    :type genre: str
    """

    def __init__(self, count: int = 5, genre: str = "mixed") -> None:
        self.count = count
        self.genre = genre

    def build(self, **kwargs: Any) -> str:
        """Render the create-tests goal string.

        :returns: Goal string.
        :rtype: str
        """
        genre_hint = (
            f"Use {self.genre} genre covers."
            if self.genre != "mixed"
            else "Use a variety of genres."
        )
        return (
            f"Create {self.count} A/B tests on the book cover testing platform. "
            f"{genre_hint} "
            "For each test: fetch two different book covers, log in as admin if not already, "
            "navigate to the test creation page, fill in the test name and paste the two "
            "cover URLs, and submit. Take a screenshot after each submission to confirm it "
            "worked. Report how many tests were successfully created."
        )


class VoteGoal(GoalTemplate):
    """Goal: have a single user vote on existing tests.

    :param username: Voter's username.
    :type username: str
    :param password: Voter's password.
    :type password: str
    :param vote_count: Number of tests to vote on.  Defaults to ``3``.
    :type vote_count: int
    :param bias: Voting bias hint.  Defaults to ``"random"``.
    :type bias: str
    """

    _BIAS_HINTS: dict[str, str] = {
        "prefers_dark": "Prefer covers with darker colour palettes.",
        "prefers_bright": "Prefer covers with brighter, more colourful designs.",
        "prefers_illustrated": "Prefer covers with illustrated or artistic designs.",
        "random": "Vote randomly -- pick either cover.",
    }

    def __init__(
        self,
        username: str,
        password: str,
        vote_count: int = 3,
        bias: str = "random",
    ) -> None:
        self.username = username
        self.password = password
        self.vote_count = vote_count
        self.bias = bias

    def build(self, **kwargs: Any) -> str:
        """Render the vote goal string.

        :returns: Goal string.
        :rtype: str
        """
        bias_hint = self._BIAS_HINTS.get(self.bias, "Vote randomly.")
        return (
            f"Log in as user '{self.username}' (password: '{self.password}'). "
            f"Navigate to the A/B tests page and cast votes on up to {self.vote_count} tests. "
            f"{bias_hint} "
            "Take a screenshot before and after each vote to verify it registered. "
            "Report which tests you voted on and which cover you chose each time."
        )


class SimulateAllUsersGoal(GoalTemplate):
    """Goal: simulate all configured users voting.

    :param vote_count_each: Number of votes per user.  Defaults to ``2``.
    :type vote_count_each: int
    """

    def __init__(self, vote_count_each: int = 2) -> None:
        self.vote_count_each = vote_count_each

    def build(self, **kwargs: Any) -> str:
        """Render the simulate-all-users goal string.

        :returns: Goal string.
        :rtype: str
        """
        lines = [
            f"Switch to user '{u.username}', login with password '{u.password}', "
            f"then vote on {self.vote_count_each} tests (bias: {u.voting_bias})."
            for u in SIM_USERS
        ]
        steps = " Then ".join(lines)
        return (
            "Simulate a full round of voting across all users. "
            + steps
            + " After all users have voted, navigate to the dashboard or results page "
            "as admin and take a final screenshot showing the vote tallies."
        )


class FullSeedGoal(GoalTemplate):
    """Goal: create tests, run voting simulation, view results.

    :param test_count: Number of A/B tests to create.  Defaults to ``5``.
    :type test_count: int
    :param vote_rounds: Voting rounds per user.  Defaults to ``1``.
    :type vote_rounds: int
    """

    def __init__(self, test_count: int = 5, vote_rounds: int = 1) -> None:
        self.test_count = test_count
        self.vote_rounds = vote_rounds

    def build(self, **kwargs: Any) -> str:
        """Render the full-seed goal string.

        :returns: Goal string.
        :rtype: str
        """
        return (
            f"Seed the A/B testing platform with {self.test_count} tests and then simulate voting. "
            "Step 1: As admin, create the tests using real book cover images from Open Library. "
            f"Step 2: Have each simulated user vote on all available tests ({self.vote_rounds} round). "
            "Step 3: As admin, view the results dashboard and take a final screenshot. "
            "Report a summary of everything that was done."
        )


# ---------------------------------------------------------------------------
# Legacy helpers kept for backwards compatibility
# ---------------------------------------------------------------------------


def goal_create_tests(count: int = 5, genre: str = "mixed") -> str:
    """Build a create-tests goal string.

    .. deprecated::
        Use :class:`CreateTestsGoal` directly.

    :param count: Number of tests to create.
    :type count: int
    :param genre: Book genre.
    :type genre: str
    :returns: Goal string.
    :rtype: str
    """
    return CreateTestsGoal(count=count, genre=genre).build()


def goal_vote_on_tests(
    username: str,
    password: str,
    vote_count: int = 3,
    bias: str = "random",
) -> str:
    """Build a vote-on-tests goal string.

    .. deprecated::
        Use :class:`VoteGoal` directly.

    :param username: Voter's username.
    :type username: str
    :param password: Voter's password.
    :type password: str
    :param vote_count: Number of tests to vote on.
    :type vote_count: int
    :param bias: Voting bias.
    :type bias: str
    :returns: Goal string.
    :rtype: str
    """
    return VoteGoal(
        username=username, password=password, vote_count=vote_count, bias=bias
    ).build()


def goal_simulate_all_users(vote_count_each: int = 2) -> str:
    """Build a simulate-all-users goal string.

    .. deprecated::
        Use :class:`SimulateAllUsersGoal` directly.

    :param vote_count_each: Votes per user.
    :type vote_count_each: int
    :returns: Goal string.
    :rtype: str
    """
    return SimulateAllUsersGoal(vote_count_each=vote_count_each).build()


def goal_full_seed(test_count: int = 5, vote_rounds: int = 1) -> str:
    """Build a full-seed goal string.

    .. deprecated::
        Use :class:`FullSeedGoal` directly.

    :param test_count: Number of A/B tests to create.
    :type test_count: int
    :param vote_rounds: Voting rounds per user.
    :type vote_rounds: int
    :returns: Goal string.
    :rtype: str
    """
    return FullSeedGoal(test_count=test_count, vote_rounds=vote_rounds).build()
