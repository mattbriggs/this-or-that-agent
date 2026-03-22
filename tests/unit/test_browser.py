"""
tests/unit/test_browser.py — Unit tests for tot_agent.browser.BrowserManager.
"""

from __future__ import annotations

import base64
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestBrowserManagerLifecycle:
    """Tests for __aenter__ / __aexit__ lifecycle."""

    async def test_aenter_raises_without_playwright(self):
        from tot_agent.browser import BrowserManager

        bm = BrowserManager(headless=True)
        with patch.dict(sys.modules, {"playwright": None, "playwright.async_api": None}):
            with pytest.raises(RuntimeError, match="playwright is not installed"):
                await bm.__aenter__()

    async def test_aenter_launches_browser_and_returns_self(self):
        """Lines 94-100: happy path through __aenter__."""
        from tot_agent.browser import BrowserManager

        bm = BrowserManager(headless=True)
        mock_pw = MagicMock()
        mock_browser = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_obj = AsyncMock()
        mock_playwright_obj.start = AsyncMock(return_value=mock_pw)

        with patch("playwright.async_api.async_playwright", return_value=mock_playwright_obj):
            result = await bm.__aenter__()

        assert result is bm
        assert bm._pw is mock_pw
        assert bm._browser is mock_browser

    async def test_aexit_closes_all_contexts(self, mock_browser, mock_context, mock_page):
        from tot_agent.browser import BrowserManager

        bm = BrowserManager(headless=True)
        bm._browser = mock_browser
        bm._pw = AsyncMock()
        bm._pw.stop = AsyncMock()
        bm._contexts["user1"] = (mock_context, mock_page)
        bm._contexts["user2"] = (mock_context, mock_page)
        await bm.__aexit__(None, None, None)
        assert mock_context.close.call_count == 2


class TestSwitchUser:
    async def test_creates_context_on_first_switch(self, browser_manager):
        assert browser_manager.active_user == "test_user"

    async def test_switch_sets_active_user(self, browser_manager, mock_browser):
        mock_ctx2 = AsyncMock()
        mock_page2 = AsyncMock()
        mock_page2.url = "http://localhost:4321/"
        mock_ctx2.new_page = AsyncMock(return_value=mock_page2)
        mock_browser.new_context = AsyncMock(return_value=mock_ctx2)
        await browser_manager.switch_user("alice")
        assert browser_manager.active_user == "alice"

    async def test_switch_returns_status_result(self, browser_manager):
        result = await browser_manager.switch_user("test_user")
        assert result["ok"] is True
        assert result["data"]["username"] == "test_user"


class TestEnsureContext:
    async def test_raises_when_browser_not_started(self):
        """Line 126: _ensure_context raises RuntimeError when _browser is None."""
        from tot_agent.browser import BrowserManager

        bm = BrowserManager()  # _browser is None
        with pytest.raises(RuntimeError, match="Browser not started"):
            await bm.switch_user("alice")


class TestActivePage:
    async def test_active_page_returns_page(self, browser_manager, mock_page):
        assert browser_manager.active_page is mock_page

    def test_raises_when_no_active_user(self):
        from tot_agent.browser import BrowserManager

        bm = BrowserManager()
        with pytest.raises(RuntimeError, match="No active user context"):
            _ = bm.active_page


class TestNavigate:
    async def test_prepends_site_url_for_relative_path(self, browser_manager, mock_page):
        result = await browser_manager.navigate("/login")
        mock_page.goto.assert_awaited_once()
        called_url = mock_page.goto.call_args[0][0]
        assert called_url.endswith("/login")
        assert "http" in called_url
        assert result["ok"] is True

    async def test_absolute_url_used_as_is(self, browser_manager, mock_page):
        result = await browser_manager.navigate("https://example.com/page")
        called_url = mock_page.goto.call_args[0][0]
        assert called_url == "https://example.com/page"
        assert result["data"]["url"] == "https://example.com/page"

    async def test_returns_confirmation_string(self, browser_manager):
        result = await browser_manager.navigate("/dashboard")
        assert result["ok"] is True
        assert "Navigated" in result["message"]

    async def test_returns_error_payload_on_navigation_failure(self, browser_manager, mock_page):
        mock_page.goto = AsyncMock(side_effect=Exception("navigation boom"))
        result = await browser_manager.navigate("/dashboard")
        assert result["ok"] is False
        assert "navigation boom" in result["error"]


class TestScreenshot:
    async def test_returns_base64_png(self, browser_manager, mock_page):
        mock_page.screenshot = AsyncMock(return_value=b"PNG_DATA")
        result = await browser_manager.screenshot()
        assert result == base64.b64encode(b"PNG_DATA").decode()


class TestClick:
    async def test_css_selector_success(self, browser_manager, mock_page):
        result = await browser_manager.click("button[type=submit]")
        assert result["ok"] is True
        assert result["data"]["strategy"] == "css"
        mock_page.click.assert_awaited()

    async def test_falls_back_to_text_matching(self, browser_manager, mock_page):
        mock_page.click = AsyncMock(side_effect=Exception("not found"))
        text_locator = AsyncMock()
        text_locator.first = AsyncMock()
        text_locator.first.click = AsyncMock()
        mock_page.get_by_text = MagicMock(return_value=text_locator)
        result = await browser_manager.click("Sign in")
        assert result["ok"] is True
        assert result["data"]["strategy"] == "text"

    async def test_returns_error_payload_when_both_fail(self, browser_manager, mock_page):
        mock_page.click = AsyncMock(side_effect=Exception("css fail"))
        text_locator = AsyncMock()
        text_locator.first = AsyncMock()
        text_locator.first.click = AsyncMock(side_effect=Exception("text fail"))
        mock_page.get_by_text = MagicMock(return_value=text_locator)
        result = await browser_manager.click("nonexistent")
        assert result["ok"] is False
        assert "text fail" in result["error"]


class TestFill:
    async def test_fill_returns_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.fill("input#email", "user@example.com")
        assert result["ok"] is True
        assert "Filled" in result["message"]
        mock_page.fill.assert_awaited_once()

    async def test_fill_returns_error_on_exception(self, browser_manager, mock_page):
        mock_page.fill = AsyncMock(side_effect=Exception("element not found"))
        result = await browser_manager.fill("#bad-selector", "value")
        assert result["ok"] is False
        assert "element not found" in result["error"]


class TestSelectOption:
    async def test_select_option_returns_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.select_option("select#genre", "fantasy")
        assert result["ok"] is True
        assert result["data"]["value"] == "fantasy"
        mock_page.select_option.assert_awaited_once()

    async def test_select_option_returns_error_on_exception(self, browser_manager, mock_page):
        mock_page.select_option = AsyncMock(side_effect=Exception("bad select"))
        result = await browser_manager.select_option("select#genre", "fantasy")
        assert result["ok"] is False
        assert "bad select" in result["error"]


class TestGetPageText:
    async def test_truncates_long_text(self, browser_manager, mock_page):
        mock_page.inner_text = AsyncMock(return_value="x" * 5000)
        result = await browser_manager.get_page_text()
        assert result["ok"] is True
        assert len(result["data"]["text"]) == 4000
        assert result["data"]["truncated"] is True

    async def test_returns_short_text_as_is(self, browser_manager, mock_page):
        mock_page.inner_text = AsyncMock(return_value="Hello world")
        result = await browser_manager.get_page_text()
        assert result["data"]["text"] == "Hello world"


class TestGetPageUrl:
    async def test_returns_page_url(self, browser_manager):
        result = await browser_manager.get_page_url()
        assert result["ok"] is True
        assert "localhost" in result["data"]["url"]


class TestWaitForSelector:
    async def test_returns_confirmation_on_success(self, browser_manager):
        result = await browser_manager.wait_for_selector(".my-element")
        assert result["ok"] is True
        assert result["data"]["selector"] == ".my-element"

    async def test_returns_timeout_message_on_failure(self, browser_manager, mock_page):
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        result = await browser_manager.wait_for_selector(".missing")
        assert result["ok"] is False
        assert result["recoverable"] is True
        assert "Timeout" in result["error"]


class TestPressKey:
    async def test_press_key_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.press_key("Enter")
        assert result["ok"] is True
        assert result["data"]["key"] == "Enter"
        mock_page.keyboard.press.assert_awaited_once_with("Enter")

    async def test_press_key_returns_failure_on_error(self, browser_manager, mock_page):
        """Lines 392-394: press_key failure branch."""
        mock_page.keyboard.press = AsyncMock(side_effect=Exception("Key error"))
        result = await browser_manager.press_key("Enter")
        assert result["ok"] is False
        assert "Key error" in result["error"]


class TestScrollDown:
    async def test_scroll_down_confirmation(self, browser_manager, mock_page):
        result = await browser_manager.scroll_down()
        assert result["ok"] is True
        mock_page.keyboard.press.assert_awaited_once_with("End")

    async def test_scroll_down_returns_failure_on_error(self, browser_manager, mock_page):
        """Lines 415-417: scroll_down failure branch."""
        mock_page.keyboard.press = AsyncMock(side_effect=Exception("Scroll error"))
        result = await browser_manager.scroll_down()
        assert result["ok"] is False
        assert "Scroll error" in result["error"]


class TestEvaluate:
    async def test_returns_stringified_result(self, browser_manager, mock_page):
        mock_page.evaluate = AsyncMock(return_value=42)
        result = await browser_manager.evaluate("1+1")
        assert result["ok"] is True
        assert result["data"]["result"] == "42"

    async def test_returns_error_on_js_exception(self, browser_manager, mock_page):
        mock_page.evaluate = AsyncMock(side_effect=Exception("SyntaxError"))
        result = await browser_manager.evaluate("this is not valid JS")
        assert result["ok"] is False
        assert "SyntaxError" in result["error"]


class TestWaitForPageReady:
    async def test_returns_confirmation_on_success(self, browser_manager, mock_page):
        result = await browser_manager.wait_for_page_ready()
        assert result["ok"] is True
        mock_page.wait_for_load_state.assert_awaited_once()

    async def test_returns_recoverable_failure_when_no_load_observed(self, browser_manager, mock_page):
        mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("No navigation"))
        result = await browser_manager.wait_for_page_ready()
        assert result["ok"] is False
        assert result["recoverable"] is True


class TestUploadFile:
    async def test_upload_file_success(self, browser_manager, mock_page):
        result = await browser_manager.upload_file("input[type='file']", "/tmp/cover_abc.jpg")
        assert result["ok"] is True
        assert result["data"]["selector"] == "input[type='file']"
        mock_page.set_input_files.assert_awaited_once()

    async def test_upload_file_returns_failure_on_error(self, browser_manager, mock_page):
        mock_page.set_input_files = AsyncMock(side_effect=Exception("No such element"))
        result = await browser_manager.upload_file("input[type='file']", "/tmp/cover_abc.jpg")
        assert result["ok"] is False
        assert "No such element" in result["error"]
