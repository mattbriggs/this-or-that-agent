"""
tests/unit/test_cli.py — Offline CLI tests using Click's CliRunner.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tot_agent.covers import BookCover


class TestCli:
    def test_info_command_renders_configuration(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "Runtime Configuration" in result.output
        assert "site_url" in result.output

    def test_users_command_lists_simulated_users(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["users"])
        assert result.exit_code == 0
        assert "Simulated Users" in result.output
        assert "admin" in result.output

    def test_create_command_builds_goal_and_runs_agent(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.cli._run_agent") as run_agent:
            result = runner.invoke(cli, ["create", "--count", "2", "--genre", "horror"])
        assert result.exit_code == 0
        run_agent.assert_called_once()
        goal_text = run_agent.call_args.args[0]
        assert "2" in goal_text
        assert "horror" in goal_text

    def test_goal_command_passes_text_to_runner(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.cli._run_agent") as run_agent:
            result = runner.invoke(cli, ["goal", "Take a screenshot"])
        assert result.exit_code == 0
        assert run_agent.call_args.args[0] == "Take a screenshot"

    def test_vote_command_rejects_unknown_user(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["vote", "--user", "nobody"])
        assert result.exit_code != 0
        assert "Unknown user" in result.output

    def test_covers_command_renders_results(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        fake_covers = [
            BookCover("Dune", "Frank Herbert", "https://img/dune.jpg", "openlibrary"),
            BookCover("Foundation", "Isaac Asimov", "https://img/foundation.jpg", "googlebooks"),
        ]
        with patch("tot_agent.covers.CoverFetcher.fetch", return_value=fake_covers):
            with patch("tot_agent.covers.verify_cover_url", side_effect=[True, False]):
                result = runner.invoke(cli, ["covers", "sci-fi", "--count", "2", "--verify"])
        assert result.exit_code == 0
        assert "Dune" in result.output
        assert "Foundation" in result.output

    def test_covers_command_handles_empty_results(self):
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.covers.CoverFetcher.fetch", return_value=[]):
            result = runner.invoke(cli, ["covers", "sci-fi"])
        assert result.exit_code == 0
        assert "No covers found" in result.output

    def test_configure_logging_adds_file_handler(self, tmp_path):
        """Line 63: FileHandler branch in _configure_logging."""
        from tot_agent.cli import _configure_logging

        log_file = str(tmp_path / "agent.log")
        with patch("logging.basicConfig") as mock_basic:
            _configure_logging("WARNING", log_file=log_file)
            _, kwargs = mock_basic.call_args
            handler_types = [type(h).__name__ for h in kwargs["handlers"]]
            assert "FileHandler" in handler_types

    def test_run_agent_body_executes(self):
        """Lines 92-111: exercise _run_agent up to asyncio.run."""
        from tot_agent.cli import _run_agent

        with patch("asyncio.run") as mock_run:
            _run_agent("Test goal", False, None, None, None)
        mock_run.assert_called_once()
        # Close the coroutine so Python doesn't warn about it being unawaited.
        mock_run.call_args[0][0].close()

    def test_vote_command_with_valid_user(self):
        """Lines 199-200: vote command happy path with a known user."""
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.cli._run_agent") as run_agent:
            result = runner.invoke(cli, ["vote", "--user", "alice"])
        assert result.exit_code == 0
        run_agent.assert_called_once()
        goal_text = run_agent.call_args.args[0]
        assert "alice" in goal_text

    def test_simulate_command(self):
        """Lines 210-212: simulate command builds goal and calls _run_agent."""
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.cli._run_agent") as run_agent:
            result = runner.invoke(cli, ["simulate", "--votes-each", "3"])
        assert result.exit_code == 0
        run_agent.assert_called_once()

    def test_seed_command(self):
        """Lines 223-225: seed command builds goal and calls _run_agent."""
        from tot_agent.cli import cli

        runner = CliRunner()
        with patch("tot_agent.cli._run_agent") as run_agent:
            result = runner.invoke(cli, ["seed", "--tests", "3", "--vote-rounds", "2"])
        assert result.exit_code == 0
        run_agent.assert_called_once()
