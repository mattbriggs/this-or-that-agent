"""
tests/unit/test_config.py — Unit tests for tot_agent.config.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestSimUser:
    """Tests for the SimUser dataclass."""

    def test_display_name_defaults_to_username(self):
        from tot_agent.config import SimUser
        u = SimUser(username="alice", password="pw")
        assert u.display_name == "alice"

    def test_display_name_set_explicitly(self):
        from tot_agent.config import SimUser
        u = SimUser(username="alice", password="pw", display_name="Alice Smith")
        assert u.display_name == "Alice Smith"

    def test_voting_bias_default(self):
        from tot_agent.config import SimUser
        u = SimUser(username="x", password="y")
        assert u.voting_bias == "random"

    def test_repr_contains_username(self):
        from tot_agent.config import SimUser
        u = SimUser(username="bob", password="pw", voting_bias="prefers_dark")
        assert "bob" in repr(u)
        assert "prefers_dark" in repr(u)


class TestGetUser:
    """Tests for the get_user() helper."""

    def test_returns_matching_user(self):
        from tot_agent.config import get_user, SIM_USERS
        first = SIM_USERS[0]
        result = get_user(first.username)
        assert result is first

    def test_returns_none_for_unknown(self):
        from tot_agent.config import get_user
        assert get_user("nonexistent_user_xyz") is None

    def test_case_sensitive(self):
        from tot_agent.config import get_user
        # "admin" exists, "Admin" should not match (case-sensitive)
        assert get_user("Admin") is None


class TestEnvironmentVariables:
    """Tests for environment-based configuration loading."""

    def test_site_url_default(self):
        from tot_agent.config import SITE_URL
        # Without env override, should still be a non-empty string
        assert isinstance(SITE_URL, str)
        assert SITE_URL.startswith("http")

    def test_agent_model_default(self):
        from tot_agent.config import AGENT_MODEL
        assert isinstance(AGENT_MODEL, str)
        assert len(AGENT_MODEL) > 0

    def test_max_agent_steps_is_positive_int(self):
        from tot_agent.config import MAX_AGENT_STEPS
        assert isinstance(MAX_AGENT_STEPS, int)
        assert MAX_AGENT_STEPS > 0

    def test_screenshot_dimensions_positive(self):
        from tot_agent.config import SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT
        assert SCREENSHOT_WIDTH > 0
        assert SCREENSHOT_HEIGHT > 0


class TestRoutes:
    """Tests for the ROUTES dictionary."""

    def test_required_keys_present(self):
        from tot_agent.config import ROUTES
        for key in ("login", "tests", "create_test", "dashboard"):
            assert key in ROUTES, f"Missing route key: {key}"

    def test_all_routes_start_with_slash(self):
        from tot_agent.config import ROUTES
        for key, path in ROUTES.items():
            assert path.startswith("/"), f"Route {key!r} should start with '/'"


class TestSimUsers:
    """Tests for the SIM_USERS list."""

    def test_has_at_least_one_user(self):
        from tot_agent.config import SIM_USERS
        assert len(SIM_USERS) >= 1

    def test_all_have_usernames(self):
        from tot_agent.config import SIM_USERS
        for u in SIM_USERS:
            assert u.username, "Every SimUser must have a non-empty username"

    def test_all_have_passwords(self):
        from tot_agent.config import SIM_USERS
        for u in SIM_USERS:
            assert u.password, "Every SimUser must have a non-empty password"

    def test_no_duplicate_usernames(self):
        from tot_agent.config import SIM_USERS
        usernames = [u.username for u in SIM_USERS]
        assert len(usernames) == len(set(usernames)), "Duplicate usernames found"
