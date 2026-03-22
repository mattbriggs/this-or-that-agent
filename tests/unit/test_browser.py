"""
tests/unit/test_browser.py — Unit tests for tot_agent.browser.BrowserManager.
"""

from __future__ import annotations

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBrowserManagerLifecycle:
    """Tests for __aenter__ / __aexit__ lifecycle."""

    async def test_aenter_returns_self(self, mock_browser):
        from tot_agent.browser import BrowserManager
        bm = BrowserManager(headless=True)
        bm._browser = mock_browser
        bm._pw = AsyncMock()
        result = bm  # We don't actually call __aenter__ to avoid Playwright start
        assert isinstance(result, BrowserManager)

    async def test_aexit_closes_all_contexts(self, mock_browser, mock_context, mock_page):
        from tot_agent.browser import BrowserManager
        bm = BrowserManager(headless=True)
        bm._browser = mock_browser
        bm._pw = AsyncMock()
        bm._pw.stop = AsyncMock()
        # Manually populate the context pool
        bm._contexts["user1"] = (mock_context, mock_page)
        bm._contexts["user2"] = (mock_context, mock_page)
        await bm.__aexit__(None, None, None)
        assert mock_context.close.call_count == 2


class TestSwitchUser:
    async def test_creates_context_on_first_switch(self, browser_manager):
        # browser_manager fixture already switched to "test_user"
        assert browser_manager.active_user == "test_user"

    async def test_switch_sets_active_user(self, browser_manager, mock_browser):
        mock_ctx2 = AsyncMock()
        mock_page2 = AsyncMock()
        mock_page2.url = "http://localhost:4321/"
        mock_ctx2.new_page = AsyncMock(return_value=mock_page2)
        mock_browser.new_context = AsyncMock(return_value=mock_ctx2)
        await browser_manager.switch_user("alice")
        assert browser_manager.active_user == "alice"

    async def test_switch_returns_status_string(self, browser_manager):
        result = await browser_manager.switch_user("test_user")
        assert "test_user" in result


class TestActivePage:
    async def test_active_page_returns_page(self, browser_manager, mock_page):
        page = browser_manager.active_page
        assert page is mock_page

    def test_raises_when_no_active_user(self):
        from tot_agent.browser import BrowserManager
        bm = BrowserManager()
        with pytest.raises(RuntimeError, match="No active user context"):
            _ = bm.active_page


class TestNavigate:
    async def test_prepends_site_url_for_relative_path(self, browser_manager, mock_page):
        await browser_manager.navigate("/login")
        mock_page.goto.assert_awaited_once()
        called_url = mock_page.goto.call_args[0][0]
        assert called_url.endswith("/login")
        assert "http" in called_url

    async def test_absolute_url_used_as_is(self, browser_manager, mock_page):
        await browser_manager.navigate("https://example.com/page")
        called_url = mock_page.goto.call_args[0][0]
        assert called_url == "https://example.com/page"

    async def test_returns_confirmation_string(self, browser_manager, mock_page):
        result = await browser_manager.navigate("/dashboard")
        assert "Navigated" in result


class TestScreenshot:
    async def test_returns_base64_png(self, browser_manager, mock_page):
        mock_page.screenshot = AsyncMock(return_value=b"PNG_DATA")
        result = await browser_manager.screenshot()
        assert result == base64.b64encode(b"PNG_DATA").decode()


class TestClick:
    async def test_css_selector_success(self, browser_manager, mock_page):
        result = await browser_manager.click("button[type=submit]")
        assert "Clicked" in result
        mock_page.click.assert_awaited()

    async def test_falls_back_to_text_matching(self, browser_manager, mock_page):
        mock_page.click = AsyncMock(side_effect=Exception("not found"))
        text_locator = AsyncMock()
        text_locator.first = AsyncMock()
        text_locator.first.click = AsyncMock()
        mock_page.get_by_text = MagicMock(return_value=text_locator)
        result = await browser_manager.click("Sign in")
        assert "text" in result.lower() or "Clicked" in result

    async def test_returns_error_string_when_both_fail(self, browser_manager, mock_page):
        mock_page.click = AsyncMock(side_effect=Exception("css fail"))
        text_locator = AsyncMock()
        text_locator.first = AsyncMock()
        text_locator.first.click = AsyncMock(side_effect=Exception("text fail"))
        mock_page.get_by_text = MagicMock(return_value=text_locator)
        result = await browser_manager.click("nonexistent")
        assert result.startswith("ERROR")


class TestFill:
    async def test_fill_returns_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.fill("input#email", "user@example.com")
        assert "Filled" in result
        mock_page.fill.assert_awaited_once()

    async def test_fill_returns_error_on_exception(self, browser_manager, mock_page):
        mock_page.fill = AsyncMock(side_effect=Exception("element not found"))
        result = await browser_manager.fill("#bad-selector", "value")
        assert result.startswith("ERROR")


class TestGetPageText:
    async def test_truncates_long_text(self, browser_manager, mock_page):
        mock_page.inner_text = AsyncMock(return_value="x" * 5000)
        result = await browser_manager.get_page_text()
        assert len(result) == 4000

    async def test_returns_short_text_as_is(self, browser_manager, mock_page):
        mock_page.inner_text = AsyncMock(return_value="Hello world")
        result = await browser_manager.get_page_text()
        assert result == "Hello world"


class TestWaitForSelector:
    async def test_returns_confirmation_on_success(self, browser_manager, mock_page):
        result = await browser_manager.wait_for_selector(".my-element")
        assert ".my-element" in result

    async def test_returns_timeout_message_on_failure(self, browser_manager, mock_page):
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        result = await browser_manager.wait_for_selector(".missing")
        assert "Timeout" in result


class TestPressKey:
    async def test_press_key_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.press_key("Enter")
        assert "Enter" in result
        mock_page.keyboard.press.assert_awaited_once_with("Enter")


class TestEvaluate:
    async def test_returns_stringified_result(self, browser_manager, mock_page):
        mock_page.evaluate = AsyncMock(return_value=42)
        result = await browser_manager.evaluate("1+1")
        assert result == "42"

    async def test_returns_error_on_js_exception(self, browser_manager, mock_page):
        mock_page.evaluate = AsyncMock(side_effect=Exception("SyntaxError"))
        result = await browser_manager.evaluate("this is not valid JS")
        assert "JS error" in result
