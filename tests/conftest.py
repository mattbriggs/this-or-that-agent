"""
conftest.py — Shared pytest fixtures for the tot_agent test suite.

Fixtures defined here are automatically available to all tests under the
``tests/`` directory without explicit import.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Browser / Playwright fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_page():
    """A :class:`unittest.mock.AsyncMock` simulating a Playwright Page."""
    page = AsyncMock()
    page.url = "http://localhost:4321/"
    page.goto = AsyncMock(return_value=None)
    page.click = AsyncMock(return_value=None)
    page.fill = AsyncMock(return_value=None)
    page.select_option = AsyncMock(return_value=None)
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    page.inner_text = AsyncMock(return_value="Page text content")
    page.wait_for_selector = AsyncMock(return_value=None)
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock(return_value=None)
    page.evaluate = AsyncMock(return_value="js_result")
    page.get_by_text = MagicMock(return_value=AsyncMock())
    return page


@pytest.fixture
def mock_context(mock_page):
    """A mock Playwright BrowserContext that returns *mock_page*."""
    ctx = AsyncMock()
    ctx.new_page = AsyncMock(return_value=mock_page)
    ctx.close = AsyncMock(return_value=None)
    return ctx


@pytest.fixture
def mock_browser(mock_context):
    """A mock Playwright Browser that returns *mock_context*."""
    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=mock_context)
    browser.close = AsyncMock(return_value=None)
    return browser


@pytest.fixture
async def browser_manager(mock_browser):
    """A :class:`~tot_agent.browser.BrowserManager` with Playwright mocked out."""
    from tot_agent.browser import BrowserManager

    bm = BrowserManager(headless=True)
    bm._browser = mock_browser
    bm._pw = AsyncMock()
    bm._pw.stop = AsyncMock(return_value=None)
    await bm.switch_user("test_user")
    return bm


# ---------------------------------------------------------------------------
# Anthropic client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anthropic_client():
    """A mock :class:`anthropic.Anthropic` client."""
    client = MagicMock()
    client.messages = MagicMock()
    return client


# ---------------------------------------------------------------------------
# HTTP fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def open_library_response():
    """Sample Open Library search JSON response with two books with covers."""
    return {
        "docs": [
            {
                "title": "Dune",
                "author_name": ["Frank Herbert"],
                "cover_i": 12345,
                "isbn": ["9780441013593"],
            },
            {
                "title": "Foundation",
                "author_name": ["Isaac Asimov"],
                "cover_i": 67890,
                "isbn": ["9780553293357"],
            },
            {
                "title": "No Cover Book",
                # Intentionally missing cover_i
                "author_name": ["Nobody"],
            },
        ]
    }


@pytest.fixture
def google_books_response():
    """Sample Google Books API JSON response."""
    return {
        "items": [
            {
                "volumeInfo": {
                    "title": "Neuromancer",
                    "authors": ["William Gibson"],
                    "imageLinks": {
                        "thumbnail": "http://books.google.com/books/content?id=abc",
                        "large": "http://books.google.com/books/content?id=abc&zoom=2",
                    },
                }
            },
            {
                "volumeInfo": {
                    "title": "No Image Book",
                    "authors": ["Author X"],
                    # No imageLinks
                }
            },
        ]
    }
