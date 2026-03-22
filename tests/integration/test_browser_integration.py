"""
tests/integration/test_browser_integration.py — Integration tests.

Integration coverage is opt-in. Set ``RUN_INTEGRATION_TESTS=1`` to run live
Playwright checks, and ``RUN_NETWORK_TESTS=1`` to additionally hit real
upstream cover APIs.
"""

from __future__ import annotations

import os

import pytest


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


RUN_INTEGRATION = _env_truthy("RUN_INTEGRATION_TESTS")
SKIP_INTEGRATION = _env_truthy("SKIP_INTEGRATION")
RUN_NETWORK = _env_truthy("RUN_NETWORK_TESTS")
SKIP_NETWORK = _env_truthy("SKIP_NETWORK_TESTS")

pytestmark = pytest.mark.skipif(
    SKIP_INTEGRATION or not RUN_INTEGRATION,
    reason="Integration tests are opt-in. Set RUN_INTEGRATION_TESTS=1 to run them.",
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
        assert result["ok"] is True
        assert result["data"]["url"] == "about:blank"

    async def test_screenshot_returns_bytes(self, live_browser):
        """screenshot() returns non-empty base64 data for a real page."""
        await live_browser.switch_user("integration_test")
        await live_browser.navigate("about:blank")
        b64 = await live_browser.screenshot()
        import base64

        raw = base64.b64decode(b64)
        assert raw[:4] == b"\x89PNG"

    async def test_get_page_url(self, live_browser):
        """get_page_url() reflects the actual page URL."""
        await live_browser.switch_user("integration_test")
        await live_browser.navigate("about:blank")
        result = await live_browser.get_page_url()
        assert result["data"]["url"] == "about:blank"

    async def test_multiple_user_contexts_are_isolated(self, live_browser):
        """Two user contexts maintain separate URLs."""
        await live_browser.switch_user("user_a")
        await live_browser.navigate("about:blank")

        await live_browser.switch_user("user_b")
        await live_browser.navigate("about:blank#b")

        await live_browser.switch_user("user_a")
        url_a = await live_browser.get_page_url()
        assert "b" not in url_a["data"]["url"]


# ---------------------------------------------------------------------------
# CoverFetcher integration (hits live Open Library API)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    SKIP_NETWORK or not RUN_NETWORK,
    reason="Network tests are opt-in. Set RUN_NETWORK_TESTS=1 to run them.",
)
class TestCoverFetcherIntegration:
    """Live network tests — require internet access."""

    def test_fetch_returns_covers_from_open_library(self):
        from tot_agent.covers import OpenLibrarySource

        source = OpenLibrarySource(timeout=15)
        covers = source.search("science fiction", limit=5)
        assert isinstance(covers, list)
        for cover in covers:
            assert cover.cover_url.startswith("https://")
            assert cover.source == "openlibrary"

    def test_cover_fetcher_deduplicates(self):
        from tot_agent.covers import CoverFetcher

        fetcher = CoverFetcher()
        covers = fetcher.fetch("fantasy", count=3)
        titles_lower = [cover.title.lower().strip() for cover in covers]
        assert len(titles_lower) == len(set(titles_lower))
