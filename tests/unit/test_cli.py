"""
tests/unit/test_cli.py — Offline CLI tests using Click's CliRunner.
"""

from __future__ import annotations

from unittest.mock import patch

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
