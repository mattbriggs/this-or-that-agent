"""
browser.py — Playwright browser manager.

Maintains a pool of named browser contexts so the agent can switch between
simulated users without re-launching the browser.  Each context has isolated
cookies / session storage, simulating a distinct logged-in user.

Usage::

    async with BrowserManager(headless=True) as bm:
        await bm.switch_user("admin")
        await bm.navigate("/dashboard")
        b64_png = await bm.screenshot()
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from tot_agent.config import ROUTES, SCREENSHOT_HEIGHT, SCREENSHOT_WIDTH, SITE_URL

logger: logging.Logger = logging.getLogger(__name__)

# User-agent string to use for all browser contexts.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


class BrowserManager:
    """Owns the Playwright instance and a pool of named browser contexts.

    Use as an async context manager::

        async with BrowserManager(headless=True) as bm:
            await bm.switch_user("alice")
            await bm.navigate("/login")

    :param headless: When ``True``, the browser runs without a visible window.
        Defaults to ``False``.
    :type headless: bool
    :param site_url: Base URL prepended to relative navigation paths.
        Defaults to :data:`~tot_agent.config.SITE_URL`.
    :type site_url: str
    """

    def __init__(
        self,
        headless: bool = False,
        site_url: str = SITE_URL,
    ) -> None:
        self.headless = headless
        self.site_url = site_url
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        # user_key -> (BrowserContext, Page)
        self._contexts: dict[str, tuple[BrowserContext, Page]] = {}
        self._active_user: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "BrowserManager":
        """Start Playwright and launch the Chromium browser.

        :returns: This :class:`BrowserManager` instance.
        :rtype: BrowserManager
        """
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox"],
        )
        logger.info("Browser launched (headless=%s)", self.headless)
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close all browser contexts and stop Playwright."""
        for user_key, (ctx, _) in self._contexts.items():
            await ctx.close()
            logger.debug("Closed context for user %r", user_key)
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser closed")

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    async def _ensure_context(self, user_key: str) -> tuple[BrowserContext, Page]:
        """Return an existing context for *user_key*, or create one.

        :param user_key: Unique identifier for the user context.
        :type user_key: str
        :returns: A ``(BrowserContext, Page)`` tuple for the user.
        :rtype: tuple[BrowserContext, Page]
        :raises RuntimeError: If the browser has not been started yet.
        """
        if self._browser is None:
            raise RuntimeError(
                "Browser not started. Use 'async with BrowserManager() as bm:'."
            )
        if user_key not in self._contexts:
            ctx = await self._browser.new_context(
                viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                user_agent=_USER_AGENT,
            )
            page = await ctx.new_page()
            self._contexts[user_key] = (ctx, page)
            logger.debug("Created browser context for user %r", user_key)
        return self._contexts[user_key]

    async def switch_user(self, user_key: str) -> str:
        """Make *user_key* the active browser context, creating it if needed.

        :param user_key: Username to switch to.
        :type user_key: str
        :returns: A status string confirming the switch.
        :rtype: str
        """
        await self._ensure_context(user_key)
        self._active_user = user_key
        logger.info("Active user context -> %r", user_key)
        return f"Switched to user context: {user_key}"

    @property
    def active_page(self) -> Page:
        """The :class:`~playwright.async_api.Page` for the active user.

        :raises RuntimeError: If no user context has been activated yet.
        """
        if not self._active_user or self._active_user not in self._contexts:
            raise RuntimeError("No active user context. Call switch_user() first.")
        return self._contexts[self._active_user][1]

    @property
    def active_user(self) -> Optional[str]:
        """Username of the currently active browser context, or ``None``."""
        return self._active_user

    # ------------------------------------------------------------------
    # Browser actions (called by agent tools)
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> str:
        """Navigate the active page to *url*.

        If *url* starts with ``/`` it is treated as a relative path and
        prepended with :attr:`site_url`.

        :param url: Absolute URL or site-relative path (e.g. ``"/login"``).
        :type url: str
        :returns: Confirmation string with the resolved URL.
        :rtype: str
        """
        if url.startswith("/"):
            url = self.site_url + url
        await self.active_page.goto(url, wait_until="networkidle", timeout=15_000)
        logger.debug("Navigated to %s", url)
        return f"Navigated to {url}"

    async def screenshot(self) -> str:
        """Capture a screenshot of the active page.

        :returns: Base64-encoded PNG image data.
        :rtype: str
        """
        png_bytes = await self.active_page.screenshot(full_page=False)
        logger.debug("Screenshot captured (%d bytes)", len(png_bytes))
        return base64.b64encode(png_bytes).decode()

    async def click(self, selector: str) -> str:
        """Click the first element matching *selector*.

        Tries CSS selector first; falls back to visible-text matching.

        :param selector: CSS selector or visible text to click.
        :type selector: str
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        page = self.active_page
        try:
            await page.click(selector, timeout=5_000)
            logger.debug("Clicked selector %r", selector)
            return f"Clicked: {selector}"
        except Exception:
            try:
                await page.get_by_text(selector, exact=False).first.click(
                    timeout=5_000
                )
                logger.debug("Clicked element by text %r", selector)
                return f"Clicked element with text: {selector}"
            except Exception as exc:
                logger.warning("Click failed for %r: %s", selector, exc)
                return f"ERROR clicking {selector!r}: {exc}"

    async def fill(self, selector: str, value: str) -> str:
        """Clear and fill an input field identified by *selector*.

        :param selector: CSS selector of the input element.
        :type selector: str
        :param value: Text to type into the field.
        :type value: str
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        try:
            await self.active_page.fill(selector, value, timeout=5_000)
            logger.debug("Filled %r", selector)
            return f"Filled {selector!r} with value"
        except Exception as exc:
            logger.warning("Fill failed for %r: %s", selector, exc)
            return f"ERROR filling {selector!r}: {exc}"

    async def select_option(self, selector: str, value: str) -> str:
        """Select a ``<select>`` option by value or label.

        :param selector: CSS selector of the ``<select>`` element.
        :type selector: str
        :param value: Option value or visible label to select.
        :type value: str
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        try:
            await self.active_page.select_option(selector, value=value, timeout=5_000)
            logger.debug("Selected option %r in %r", value, selector)
            return f"Selected option {value!r} in {selector}"
        except Exception as exc:
            logger.warning("select_option failed: %s", exc)
            return f"ERROR selecting option: {exc}"

    async def get_page_text(self) -> str:
        """Return visible body text of the active page, capped at 4 000 chars.

        :returns: Truncated visible text content.
        :rtype: str
        """
        text = await self.active_page.inner_text("body")
        logger.debug("get_page_text: %d chars", len(text))
        return text[:4000]

    async def get_page_url(self) -> str:
        """Return the current URL of the active page.

        :returns: Current page URL.
        :rtype: str
        """
        return self.active_page.url

    async def wait_for_selector(self, selector: str, timeout: int = 8_000) -> str:
        """Wait until a CSS selector appears on the page.

        Useful for waiting after form submissions or client-side route changes.

        :param selector: CSS selector to wait for.
        :type selector: str
        :param timeout: Maximum wait time in milliseconds.  Defaults to
            ``8000``.
        :type timeout: int
        :returns: Confirmation string, or a timeout error message.
        :rtype: str
        """
        try:
            await self.active_page.wait_for_selector(selector, timeout=timeout)
            logger.debug("Selector appeared: %r", selector)
            return f"Selector appeared: {selector}"
        except Exception as exc:
            logger.warning("Timeout waiting for %r: %s", selector, exc)
            return f"Timeout waiting for {selector!r}: {exc}"

    async def press_key(self, key: str) -> str:
        """Press a keyboard key on the active page.

        :param key: Playwright key name (e.g. ``"Enter"``, ``"Tab"``,
            ``"Escape"``).
        :type key: str
        :returns: Confirmation string.
        :rtype: str
        """
        await self.active_page.keyboard.press(key)
        logger.debug("Pressed key %r", key)
        return f"Pressed key: {key}"

    async def scroll_down(self) -> str:
        """Scroll the active page to the bottom.

        :returns: Confirmation string.
        :rtype: str
        """
        await self.active_page.keyboard.press("End")
        return "Scrolled to bottom"

    async def evaluate(self, js: str) -> str:
        """Execute arbitrary JavaScript in the active page context.

        :param js: JavaScript expression or statement to evaluate.
        :type js: str
        :returns: String representation of the result (capped at 1 000 chars),
            or a JS error message.
        :rtype: str
        """
        try:
            result = await self.active_page.evaluate(js)
            output = str(result)[:1000]
            logger.debug("JS evaluate result: %s", output[:80])
            return output
        except Exception as exc:
            logger.warning("JS evaluate error: %s", exc)
            return f"JS error: {exc}"
