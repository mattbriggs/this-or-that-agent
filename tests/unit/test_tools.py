"""
tests/unit/test_tools.py — Unit tests for tot_agent.tools.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestToolDefinitions:
    """Structural tests for TOOL_DEFINITIONS."""

    def test_all_tools_have_name(self):
        from tot_agent.tools import TOOL_DEFINITIONS
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"

    def test_all_tools_have_description(self):
        from tot_agent.tools import TOOL_DEFINITIONS
        for tool in TOOL_DEFINITIONS:
            assert "description" in tool
            assert len(tool["description"]) > 0

    def test_all_tools_have_input_schema(self):
        from tot_agent.tools import TOOL_DEFINITIONS
        for tool in TOOL_DEFINITIONS:
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_expected_tools_present(self):
        from tot_agent.tools import TOOL_DEFINITIONS
        expected = {
            "screenshot", "navigate", "click", "fill", "press_key",
            "get_page_text", "get_page_url", "scroll_down", "wait_for_element",
            "switch_user", "login", "fetch_book_covers",
        }
        actual = {t["name"] for t in TOOL_DEFINITIONS}
        assert expected.issubset(actual), f"Missing tools: {expected - actual}"

    def test_no_duplicate_tool_names(self):
        from tot_agent.tools import TOOL_DEFINITIONS
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names))


class TestFormatToolResult:
    """Tests for format_tool_result()."""

    def test_screenshot_result_returns_image_block(self):
        from tot_agent.tools import format_tool_result
        result = {"type": "screenshot", "data": "base64data=="}
        formatted = format_tool_result("tool123", result)
        assert formatted["type"] == "tool_result"
        assert formatted["tool_use_id"] == "tool123"
        content = formatted["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "image"
        assert content[0]["source"]["data"] == "base64data=="

    def test_string_result_returns_text(self):
        from tot_agent.tools import format_tool_result
        formatted = format_tool_result("tool456", "Navigated to /login")
        assert formatted["content"] == "Navigated to /login"

    def test_dict_result_is_json_serialised(self):
        from tot_agent.tools import format_tool_result
        result = {"key": "value", "count": 42}
        formatted = format_tool_result("tool789", result)
        parsed = json.loads(formatted["content"])
        assert parsed["key"] == "value"

    def test_list_result_is_json_serialised(self):
        from tot_agent.tools import format_tool_result
        result = [{"title": "Dune", "cover_url": "https://example.com/dune.jpg"}]
        formatted = format_tool_result("tool000", result)
        parsed = json.loads(formatted["content"])
        assert parsed[0]["title"] == "Dune"

    def test_none_result_becomes_string_none(self):
        from tot_agent.tools import format_tool_result
        formatted = format_tool_result("toolNone", None)
        assert formatted["content"] == "None"


class TestDispatch:
    """Tests for the dispatch() async function."""

    async def test_screenshot_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.screenshot = AsyncMock(return_value="b64png==")
        result = await dispatch("screenshot", {}, browser_manager)
        assert result["type"] == "screenshot"
        assert result["data"] == "b64png=="

    async def test_navigate_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.navigate = AsyncMock(return_value="Navigated to /test")
        result = await dispatch("navigate", {"url": "/test"}, browser_manager)
        assert result == "Navigated to /test"

    async def test_click_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.click = AsyncMock(return_value="Clicked: button")
        result = await dispatch("click", {"selector": "button"}, browser_manager)
        assert result == "Clicked: button"

    async def test_fill_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.fill = AsyncMock(return_value="Filled 'input' with value")
        result = await dispatch("fill", {"selector": "input", "value": "hello"}, browser_manager)
        assert "Filled" in result

    async def test_press_key_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.press_key = AsyncMock(return_value="Pressed key: Enter")
        result = await dispatch("press_key", {"key": "Enter"}, browser_manager)
        assert "Enter" in result

    async def test_get_page_text_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.get_page_text = AsyncMock(return_value="Page text")
        result = await dispatch("get_page_text", {}, browser_manager)
        assert result == "Page text"

    async def test_get_page_url_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.get_page_url = AsyncMock(return_value="http://localhost:4321/")
        result = await dispatch("get_page_url", {}, browser_manager)
        assert "localhost" in result

    async def test_scroll_down_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.scroll_down = AsyncMock(return_value="Scrolled to bottom")
        result = await dispatch("scroll_down", {}, browser_manager)
        assert "bottom" in result.lower()

    async def test_wait_for_element_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.wait_for_selector = AsyncMock(return_value="Selector appeared: .el")
        result = await dispatch("wait_for_element", {"selector": ".el"}, browser_manager)
        assert ".el" in result

    async def test_switch_user_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.switch_user = AsyncMock(return_value="Switched to user context: bob")
        result = await dispatch("switch_user", {"username": "bob"}, browser_manager)
        assert "bob" in result

    async def test_unknown_tool_returns_error(self, browser_manager):
        from tot_agent.tools import dispatch
        result = await dispatch("not_a_real_tool", {}, browser_manager)
        assert "ERROR" in result

    async def test_login_tool_calls_navigate_and_fill(self, browser_manager):
        from tot_agent.tools import dispatch
        browser_manager.navigate = AsyncMock(return_value="ok")
        browser_manager.fill = AsyncMock(return_value="ok")
        browser_manager.press_key = AsyncMock(return_value="ok")
        result = await dispatch(
            "login", {"username": "alice", "password": "pw123"}, browser_manager
        )
        assert "alice" in result
        browser_manager.navigate.assert_awaited()
        browser_manager.press_key.assert_awaited_with("Enter")

    async def test_fetch_book_covers_tool(self, browser_manager):
        from tot_agent.tools import dispatch
        from tot_agent.covers import BookCover
        fake_covers = [
            BookCover("Dune", "F. Herbert", "https://img/dune.jpg", "openlibrary"),
        ]
        with patch("tot_agent.covers.fetch_book_covers", return_value=fake_covers):
            result = await dispatch(
                "fetch_book_covers", {"query": "sci-fi", "count": 1}, browser_manager
            )
        assert isinstance(result, list)
        assert result[0]["title"] == "Dune"
        assert "cover_url" in result[0]
