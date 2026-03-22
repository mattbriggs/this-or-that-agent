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
from typing import TYPE_CHECKING, Any

from tot_agent.config import (
    ACTION_TIMEOUT_MS,
    NAVIGATION_TIMEOUT_MS,
    PAGE_READY_TIMEOUT_MS,
    SCREENSHOT_HEIGHT,
    SCREENSHOT_WIDTH,
    SITE_URL,
    WAIT_FOR_ELEMENT_TIMEOUT_MS,
)
from tot_agent.results import failure_result, success_result

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright
else:  # pragma: no cover - runtime fallback when Playwright is absent
    Browser = BrowserContext = Page = Playwright = Any

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

    :param bool headless: When ``True``, the browser runs without a visible window.
        Defaults to ``False``.
    :param str site_url: Base URL prepended to relative navigation paths.
        Defaults to :data:`~tot_agent.config.SITE_URL`.
    """

    def __init__(
        self,
        headless: bool = False,
        site_url: str = SITE_URL,
    ) -> None:
        self.headless = headless
        self.site_url = site_url
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        # user_key -> (BrowserContext, Page)
        self._contexts: dict[str, tuple[BrowserContext, Page]] = {}
        self._active_user: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> BrowserManager:
        """Start Playwright and launch the Chromium browser.

        :returns: This :class:`BrowserManager` instance.
        :rtype: BrowserManager
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - exercised in unit tests via import boundary
            raise RuntimeError(
                "playwright is not installed. Install project dependencies and run "
                "`playwright install chromium` before starting the browser."
            ) from exc

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

        :param str user_key: Unique identifier for the user context.
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

    async def switch_user(self, user_key: str) -> dict[str, Any]:
        """Make *user_key* the active browser context, creating it if needed.

        :param str user_key: Username to switch to.
        :returns: A status string confirming the switch.
        :rtype: str
        """
        await self._ensure_context(user_key)
        self._active_user = user_key
        logger.info("Active user context -> %r", user_key)
        return success_result(
            f"Switched to user context: {user_key}",
            action="switch_user",
            username=user_key,
        )

    @property
    def active_page(self) -> Page:
        """The :class:`~playwright.async_api.Page` for the active user.

        :raises RuntimeError: If no user context has been activated yet.
        """
        if not self._active_user or self._active_user not in self._contexts:
            raise RuntimeError("No active user context. Call switch_user() first.")
        return self._contexts[self._active_user][1]

    @property
    def active_user(self) -> str | None:
        """Username of the currently active browser context, or ``None``."""
        return self._active_user

    # ------------------------------------------------------------------
    # Browser actions (called by agent tools)
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate the active page to *url*.

        If *url* starts with ``/`` it is treated as a relative path and
        prepended with :attr:`site_url`.

        :param str url: Absolute URL or site-relative path (e.g. ``"/login"``).
        :returns: Confirmation string with the resolved URL.
        :rtype: str
        """
        resolved_url = self.site_url + url if url.startswith("/") else url
        try:
            await self.active_page.goto(
                resolved_url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )
        except Exception as exc:
            logger.warning("Navigation failed for %s: %s", resolved_url, exc)
            return failure_result(
                f"Navigation failed for {resolved_url}",
                error=str(exc),
                action="navigate",
                url=resolved_url,
                timeout_ms=NAVIGATION_TIMEOUT_MS,
            )

        logger.debug("Navigated to %s", resolved_url)
        return success_result(
            f"Navigated to {resolved_url}",
            action="navigate",
            url=resolved_url,
            timeout_ms=NAVIGATION_TIMEOUT_MS,
        )

    async def screenshot(self) -> str:
        """Capture a screenshot of the active page.

        :returns: Base64-encoded PNG image data.
        :rtype: str
        """
        png_bytes = await self.active_page.screenshot(full_page=False)
        logger.debug("Screenshot captured (%d bytes)", len(png_bytes))
        return base64.b64encode(png_bytes).decode()

    async def click(self, selector: str) -> dict[str, Any]:
        """Click the first element matching *selector*.

        Tries CSS selector first; falls back to visible-text matching.

        :param str selector: CSS selector or visible text to click.
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        page = self.active_page
        css_error: str | None = None
        try:
            await page.click(selector, timeout=ACTION_TIMEOUT_MS)
            logger.debug("Clicked selector %r", selector)
            return success_result(
                f"Clicked: {selector}",
                action="click",
                selector=selector,
                strategy="css",
            )
        except Exception as exc:
            css_error = str(exc)
            try:
                await page.get_by_text(selector, exact=False).first.click(timeout=ACTION_TIMEOUT_MS)
                logger.debug("Clicked element by text %r", selector)
                return success_result(
                    f"Clicked element with text: {selector}",
                    action="click",
                    selector=selector,
                    strategy="text",
                )
            except Exception as exc:
                logger.warning("Click failed for %r: %s", selector, exc)
                return failure_result(
                    f"Unable to click {selector!r}",
                    error=str(exc),
                    action="click",
                    selector=selector,
                    attempted_strategies=["css", "text"],
                    css_error=css_error,
                )

    async def fill(self, selector: str, value: str) -> dict[str, Any]:
        """Clear and fill an input field identified by *selector*.

        :param str selector: CSS selector of the input element.
        :param str value: Text to type into the field.
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        try:
            await self.active_page.fill(selector, value, timeout=ACTION_TIMEOUT_MS)
            logger.debug("Filled %r", selector)
            return success_result(
                f"Filled {selector!r} with value",
                action="fill",
                selector=selector,
                value=value,
            )
        except Exception as exc:
            logger.warning("Fill failed for %r: %s", selector, exc)
            return failure_result(
                f"Unable to fill {selector!r}",
                error=str(exc),
                action="fill",
                selector=selector,
                value=value,
            )

    async def select_option(self, selector: str, value: str) -> dict[str, Any]:
        """Select a ``<select>`` option by value or label.

        :param str selector: CSS selector of the ``<select>`` element.
        :param str value: Option value or visible label to select.
        :returns: Confirmation string, or an error message prefixed with
            ``"ERROR"``.
        :rtype: str
        """
        try:
            await self.active_page.select_option(selector, value=value, timeout=ACTION_TIMEOUT_MS)
            logger.debug("Selected option %r in %r", value, selector)
            return success_result(
                f"Selected option {value!r} in {selector}",
                action="select_option",
                selector=selector,
                value=value,
            )
        except Exception as exc:
            logger.warning("select_option failed: %s", exc)
            return failure_result(
                f"Unable to select option {value!r} in {selector}",
                error=str(exc),
                action="select_option",
                selector=selector,
                value=value,
            )

    async def get_page_text(self) -> dict[str, Any]:
        """Return visible body text of the active page, capped at 4 000 chars.

        :returns: Truncated visible text content.
        :rtype: str
        """
        text = await self.active_page.inner_text("body")
        logger.debug("get_page_text: %d chars", len(text))
        truncated = text[:4000]
        return success_result(
            "Retrieved visible page text",
            action="get_page_text",
            text=truncated,
            truncated=len(text) > len(truncated),
            character_count=len(truncated),
        )

    async def get_page_url(self) -> dict[str, Any]:
        """Return the current URL of the active page.

        :returns: Current page URL.
        :rtype: str
        """
        return success_result(
            "Retrieved current page URL",
            action="get_page_url",
            url=self.active_page.url,
        )

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int = WAIT_FOR_ELEMENT_TIMEOUT_MS,
    ) -> dict[str, Any]:
        """Wait until a CSS selector appears on the page.

        Useful for waiting after form submissions or client-side route changes.

        :param str selector: CSS selector to wait for.
        :param int timeout: Maximum wait time in milliseconds.  Defaults to
            ``8000``.
        :returns: Confirmation string, or a timeout error message.
        :rtype: str
        """
        try:
            await self.active_page.wait_for_selector(selector, timeout=timeout)
            logger.debug("Selector appeared: %r", selector)
            return success_result(
                f"Selector appeared: {selector}",
                action="wait_for_selector",
                selector=selector,
                timeout_ms=timeout,
            )
        except Exception as exc:
            logger.warning("Timeout waiting for %r: %s", selector, exc)
            return failure_result(
                f"Timed out waiting for {selector!r}",
                error=str(exc),
                action="wait_for_selector",
                selector=selector,
                timeout_ms=timeout,
                recoverable=True,
            )

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a keyboard key on the active page.

        :param str key: Playwright key name (e.g. ``"Enter"``, ``"Tab"``,
            ``"Escape"``).
        :returns: Confirmation string.
        :rtype: str
        """
        try:
            await self.active_page.keyboard.press(key)
        except Exception as exc:
            logger.warning("Key press failed for %r: %s", key, exc)
            return failure_result(
                f"Unable to press key {key}",
                error=str(exc),
                action="press_key",
                key=key,
            )
        logger.debug("Pressed key %r", key)
        return success_result(
            f"Pressed key: {key}",
            action="press_key",
            key=key,
        )

    async def scroll_down(self) -> dict[str, Any]:
        """Scroll the active page to the bottom.

        :returns: Confirmation string.
        :rtype: str
        """
        try:
            await self.active_page.keyboard.press("End")
        except Exception as exc:
            logger.warning("Scroll down failed: %s", exc)
            return failure_result(
                "Unable to scroll to the bottom of the page",
                error=str(exc),
                action="scroll_down",
            )
        return success_result("Scrolled to bottom", action="scroll_down")

    async def evaluate(self, js: str) -> dict[str, Any]:
        """Execute arbitrary JavaScript in the active page context.

        :param str js: JavaScript expression or statement to evaluate.
        :returns: String representation of the result (capped at 1 000 chars),
            or a JS error message.
        :rtype: str
        """
        try:
            result = await self.active_page.evaluate(js)
            output = str(result)[:1000]
            logger.debug("JS evaluate result: %s", output[:80])
            return success_result(
                "Executed JavaScript in the active page",
                action="evaluate",
                result=output,
            )
        except Exception as exc:
            logger.warning("JS evaluate error: %s", exc)
            return failure_result(
                "JavaScript evaluation failed",
                error=str(exc),
                action="evaluate",
            )

    async def wait_for_page_ready(
        self,
        timeout: int = PAGE_READY_TIMEOUT_MS,
    ) -> dict[str, Any]:
        """Best-effort wait for a DOM-ready state after an action.

        This is intentionally recoverable: many SPA interactions do not trigger
        a new document load, so timing out here is useful signal but not always
        a hard failure.
        """
        try:
            await self.active_page.wait_for_load_state(
                "domcontentloaded",
                timeout=timeout,
            )
        except Exception as exc:
            logger.debug("Page ready wait did not observe a new load: %s", exc)
            return failure_result(
                "No new DOM-ready state was observed after the action",
                error=str(exc),
                action="wait_for_page_ready",
                timeout_ms=timeout,
                recoverable=True,
            )

        return success_result(
            "Observed DOM-ready state after the action",
            action="wait_for_page_ready",
            timeout_ms=timeout,
        )
