"""
tests/unit/test_agent.py — Unit tests for tot_agent.agent.
"""

from __future__ import annotations

import io
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

# ---------------------------------------------------------------------------
# AgentEvent / EventType
# ---------------------------------------------------------------------------


class TestAgentEvent:
    def test_event_has_type_and_data(self):
        from tot_agent.agent import AgentEvent, EventType

        event = AgentEvent(EventType.GOAL_START, {"goal": "do something"})
        assert event.event_type == EventType.GOAL_START
        assert event.data["goal"] == "do something"

    def test_event_data_defaults_to_empty_dict(self):
        from tot_agent.agent import AgentEvent, EventType

        event = AgentEvent(EventType.STEP_START)
        assert event.data == {}


# ---------------------------------------------------------------------------
# Observer pattern
# ---------------------------------------------------------------------------


class TestConsoleObserver:
    def test_on_event_does_not_raise_for_any_event_type(self):
        from tot_agent.agent import AgentEvent, ConsoleObserver, EventType

        obs = ConsoleObserver(console=Console(file=io.StringIO()))
        for event_type in EventType:
            obs.on_event(AgentEvent(event_type, {}))


class TestLoggingObserver:
    def test_on_event_does_not_raise_for_any_event_type(self):
        from tot_agent.agent import AgentEvent, EventType, LoggingObserver

        obs = LoggingObserver(log=logging.getLogger("test_obs"))
        for event_type in EventType:
            obs.on_event(AgentEvent(event_type, {}))


class TestCustomObserver:
    def test_observer_receives_events_in_order(self):
        from tot_agent.agent import AgentEvent, AgentObserver, EventType

        received = []

        class RecordingObserver(AgentObserver):
            def on_event(self, event: AgentEvent) -> None:
                received.append(event.event_type)

        obs = RecordingObserver()
        obs.on_event(AgentEvent(EventType.GOAL_START))
        obs.on_event(AgentEvent(EventType.STEP_START))
        obs.on_event(AgentEvent(EventType.GOAL_COMPLETE))
        assert received == [
            EventType.GOAL_START,
            EventType.STEP_START,
            EventType.GOAL_COMPLETE,
        ]


# ---------------------------------------------------------------------------
# BrowserAgent
# ---------------------------------------------------------------------------


def _make_message_response(
    text: str = "Goal done.",
    stop_reason: str = "end_turn",
    tool_calls: list[dict[str, object]] | None = None,
):
    """Create a minimal mock Claude API response."""
    content = []
    if text:
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = text
        content.append(text_block)
    for tool_call in tool_calls or []:
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = tool_call["id"]
        tool_block.name = tool_call["name"]
        tool_block.input = tool_call["input"]
        content.append(tool_block)
    response = MagicMock()
    response.content = content
    response.stop_reason = stop_reason
    return response


class TestBrowserAgentRun:
    async def test_run_completes_on_end_turn(self, browser_manager, mock_anthropic_client):
        from tot_agent.agent import AgentEvent, AgentObserver, BrowserAgent, EventType

        received_events = []

        class CapturingObserver(AgentObserver):
            def on_event(self, event: AgentEvent) -> None:
                received_events.append(event)

        mock_anthropic_client.messages.create = MagicMock(
            return_value=_make_message_response("All done!")
        )

        agent = BrowserAgent(
            bm=browser_manager,
            observers=[CapturingObserver()],
            client=mock_anthropic_client,
        )

        result = await agent.run("Do something.")
        assert result == "All done!"
        event_types = [event.event_type for event in received_events]
        assert EventType.GOAL_START in event_types
        assert EventType.GOAL_COMPLETE in event_types

    async def test_run_executes_tool_call(self, browser_manager, mock_anthropic_client):
        from tot_agent.agent import BrowserAgent

        first_response = _make_message_response(
            text="",
            stop_reason="tool_use",
            tool_calls=[{"id": "tc1", "name": "screenshot", "input": {}}],
        )
        second_response = _make_message_response("Screenshot taken, done.")

        mock_anthropic_client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        agent = BrowserAgent(
            bm=browser_manager,
            observers=[],
            client=mock_anthropic_client,
        )
        browser_manager.screenshot = AsyncMock(return_value="b64data==")

        result = await agent.run("Take a screenshot.")
        assert "Screenshot taken" in result or "done" in result.lower()
        assert mock_anthropic_client.messages.create.call_count == 2

    async def test_run_returns_step_limit_message(self, browser_manager, mock_anthropic_client):
        from tot_agent.agent import BrowserAgent

        tool_response = _make_message_response(
            text="",
            stop_reason="tool_use",
            tool_calls=[{"id": "tc1", "name": "get_page_url", "input": {}}],
        )
        mock_anthropic_client.messages.create = MagicMock(return_value=tool_response)

        agent = BrowserAgent(
            bm=browser_manager,
            observers=[],
            client=mock_anthropic_client,
            max_steps=2,
        )
        browser_manager.get_page_url = AsyncMock(
            return_value={
                "ok": True,
                "message": "Retrieved current page URL",
                "data": {"url": "http://localhost/"},
            }
        )

        result = await agent.run("Loop forever.")
        assert "step limit" in result.lower() or "Reached" in result

    def test_raises_without_api_key(self, browser_manager):
        from tot_agent.agent import BrowserAgent

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            BrowserAgent(bm=browser_manager, api_key=None)

    def test_add_remove_observer(self, browser_manager, mock_anthropic_client):
        from tot_agent.agent import AgentEvent, AgentObserver, BrowserAgent

        class NoopObserver(AgentObserver):
            def on_event(self, event: AgentEvent) -> None:
                pass

        agent = BrowserAgent(
            bm=browser_manager,
            observers=[],
            client=mock_anthropic_client,
        )
        observer = NoopObserver()
        agent.add_observer(observer)
        assert observer in agent._observers
        agent.remove_observer(observer)
        assert observer not in agent._observers


# ---------------------------------------------------------------------------
# Goal template builders
# ---------------------------------------------------------------------------


class TestGoalTemplates:
    def test_create_tests_goal_contains_count(self):
        from tot_agent.agent import CreateTestsGoal

        goal = CreateTestsGoal(count=7, genre="horror").build()
        assert "7" in goal
        assert "horror" in goal

    def test_create_tests_goal_mixed_genre(self):
        from tot_agent.agent import CreateTestsGoal

        goal = CreateTestsGoal(count=3, genre="mixed").build()
        assert "variety" in goal.lower() or "mixed" not in goal

    def test_vote_goal_contains_username(self):
        from tot_agent.agent import VoteGoal

        goal = VoteGoal("alice", "pw", vote_count=5, bias="prefers_dark").build()
        assert "alice" in goal
        assert "dark" in goal.lower()

    def test_vote_goal_unknown_bias_defaults_to_random(self):
        from tot_agent.agent import VoteGoal

        goal = VoteGoal("alice", "pw", bias="unknown_bias").build()
        assert "randomly" in goal.lower() or "random" in goal.lower()

    def test_simulate_all_users_contains_all_usernames(self):
        from tot_agent.agent import SimulateAllUsersGoal
        from tot_agent.config import SIM_USERS

        goal = SimulateAllUsersGoal(vote_count_each=3).build()
        for user in SIM_USERS:
            assert user.username in goal

    def test_full_seed_goal_contains_test_count(self):
        from tot_agent.agent import FullSeedGoal

        goal = FullSeedGoal(test_count=10, vote_rounds=2).build()
        assert "10" in goal

    def test_legacy_helpers_return_strings(self):
        from tot_agent.agent import (
            goal_create_tests,
            goal_full_seed,
            goal_simulate_all_users,
            goal_vote_on_tests,
        )

        assert isinstance(goal_create_tests(), str)
        assert isinstance(goal_vote_on_tests("alice", "pw"), str)
        assert isinstance(goal_simulate_all_users(), str)
        assert isinstance(goal_full_seed(), str)
