"""
tests/integration/test_browser_integration.py — Integration tests.

These tests require a running Playwright/Chromium installation.  They are
skipped automatically when Playwright is not available or when the
``SKIP_INTEGRATION`` environment variable is set to a truthy value.

To run integration tests explicitly::

    pytest tests/integration/ -v

To skip them::

    SKIP_INTEGRATION=1 pytest
"""

from __future__ import annotations

import os
import pytest

# Skip the entire module if SKIP_INTEGRATION is set or Playwright is absent.
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION", "").strip() in ("1", "true", "yes"),
    reason="Integration tests disabled via SKIP_INTEGRATION env var",
)


def _playwright_available() -> bool:
    """Return True if the playwright package is importable."""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


playwright_required = pytest.mark.skipif(
    not _playwright_available(),
    reason="playwright package not installed",
)


# ---------------------------------------------------------------------------
# BrowserManager integration
# ---------------------------------------------------------------------------


@playwright_required
class TestBrowserManagerIntegration:
    """End-to-end tests that launch a real Chromium instance."""

    @pytest.fixture
    async def live_browser(self):
        """Launch a real headless BrowserManager and yield it."""
        from tot_agent.browser import BrowserManager
        async with BrowserManager(headless=True) as bm:
            yield bm

    async def test_switch_and_navigate_to_about_blank(self, live_browser):
        """BrowserManager can navigate a real page and return a URL."""
        await live_browser.switch_user("integration_test")
        result = await live_browser.navigate("about:blank")
        assert "about:blank" in result

    async def test_screenshot_returns_bytes(self, live_browser):
        """screenshot() returns non-empty base64 data for a real page."""
        await live_browser.switch_user("integration_test")
        await live_browser.navigate("about:blank")
        b64 = await live_browser.screenshot()
        import base64
        raw = base64.b64decode(b64)
        # PNG magic bytes
        assert raw[:4] == b"\x89PNG"

    async def test_get_page_url(self, live_browser):
        """get_page_url() reflects the actual page URL."""
        await live_browser.switch_user("integration_test")
        await live_browser.navigate("about:blank")
        url = await live_browser.get_page_url()
        assert url == "about:blank"

    async def test_multiple_user_contexts_are_isolated(self, live_browser):
        """Two user contexts maintain separate URLs."""
        await live_browser.switch_user("user_a")
        await live_browser.navigate("about:blank")

        await live_browser.switch_user("user_b")
        await live_browser.navigate("about:blank#b")

        # Switch back — user_a context should still be at about:blank
        await live_browser.switch_user("user_a")
        url_a = await live_browser.get_page_url()
        assert "b" not in url_a


# ---------------------------------------------------------------------------
# CoverFetcher integration (hits live Open Library API)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.getenv("SKIP_NETWORK_TESTS", "").strip() in ("1", "true", "yes"),
    reason="Network tests disabled via SKIP_NETWORK_TESTS env var",
)
class TestCoverFetcherIntegration:
    """Live network tests — require internet access."""

    def test_fetch_returns_covers_from_open_library(self):
        from tot_agent.covers import OpenLibrarySource
        source = OpenLibrarySource(timeout=15)
        covers = source.search("science fiction", limit=5)
        # May return 0 if the API is down; at least must not raise
        assert isinstance(covers, list)
        for c in covers:
            assert c.cover_url.startswith("https://")
            assert c.source == "openlibrary"

    def test_cover_fetcher_deduplicates(self):
        from tot_agent.covers import CoverFetcher
        fetcher = CoverFetcher()
        covers = fetcher.fetch("fantasy", count=3)
        titles_lower = [c.title.lower().strip() for c in covers]
        assert len(titles_lower) == len(set(titles_lower))
