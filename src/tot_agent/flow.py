"""
flow.py — Scripted, deterministic contest-creation flow.

Replaces the open-ended agentic loop for contest creation with a direct step
sequence that never burns tokens in a retry spiral:

    Research phase  (pure Python, no LLM)
        CoverFetcher picks a random genre, fetches a cover pair from Open
        Library / Google Books, and downloads both images to temp files.

    Browser phase   (scripted Playwright, no agentic loop)
        Steps are executed in order via BrowserManager:
        switch_user → login → navigate → fill fields → upload covers
        → submit → verify redirect → logout.
        Each step returns a structured result dict; on failure the flow
        logs and returns False immediately rather than looping.

The ContestCreationFlow class is platform-agnostic.  All routes and CSS
selectors come from a PlatformConfig instance, so targeting a different SaaS
platform requires only a new config — not a code change.

See docs/adding-a-platform.md for a guide to writing new platform configs.
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tot_agent.config import SIM_USERS, SimUser
from tot_agent.covers import CoverFetcher, download_cover_image
from tot_agent.platform import PlatformConfig, THIS_OR_THAT
from tot_agent.results import is_failure_result

if TYPE_CHECKING:
    from tot_agent.browser import BrowserManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ContestData:
    """All values needed to fill one contest-creation form.

    Produced by the research phase and consumed by the browser phase.
    No LLM is involved in building this object.

    :param str title: Contest title shown to voters.
    :param str description: Short paragraph about the comparison.
    :param str image_a_label: Edition name for cover A (e.g. "1954 Original").
    :param str image_b_label: Edition name for cover B (e.g. "1987 Reprint").
    :param str image_a_path: Absolute path to the downloaded cover-A image file.
    :param str image_b_path: Absolute path to the downloaded cover-B image file.
    :param str tags: Comma-separated keyword tags.
    """

    title: str
    description: str
    image_a_label: str
    image_b_label: str
    image_a_path: str
    image_b_path: str
    tags: str


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


class ContestCreationFlow:
    """Scripted, platform-agnostic contest-creation flow.

    Usage::

        async with BrowserManager() as bm:
            flow = ContestCreationFlow(bm, platform=THIS_OR_THAT)
            ok = await flow.run_for_user(user)

    :param BrowserManager bm: An active :class:`~tot_agent.browser.BrowserManager`.
    :param PlatformConfig platform: Routes and selectors for the target platform.
        Defaults to :data:`~tot_agent.platform.THIS_OR_THAT`.
    """

    def __init__(
        self,
        bm: BrowserManager,
        platform: PlatformConfig = THIS_OR_THAT,
    ) -> None:
        self.bm = bm
        self.platform = platform

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_for_user(self, user: SimUser) -> bool:
        """Execute one full contest-creation flow for *user*.

        Downloads cover images to temp files, runs the browser flow, then
        deletes the temp files regardless of outcome.

        :param SimUser user: The simulated user whose credentials are used.
        :returns: ``True`` if the contest was created and submitted successfully.
        :rtype: bool
        """
        logger.info("[%s] Starting contest-creation flow", user.display_name)
        data = self._research_phase()
        try:
            return await self._browser_phase(user, data)
        finally:
            for path in (data.image_a_path, data.image_b_path):
                try:
                    os.unlink(path)
                    logger.debug("Deleted temp file %s", path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Research phase
    # ------------------------------------------------------------------

    def _research_phase(self) -> ContestData:
        """Fetch a random cover pair and populate a ContestData.

        Uses :class:`~tot_agent.covers.CoverFetcher` to search Open Library
        and Google Books.  Both cover images are downloaded to temporary local
        files so Playwright can upload them directly.

        .. note::
            The two covers may come from different books within the same genre
            query.  To compare two editions of *the same* book, extend this
            method to search by exact title and filter on distinct cover IDs.

        :returns: A fully populated :class:`ContestData` instance.
        :rtype: ContestData
        :raises RuntimeError: If no cover pairs can be fetched.
        """
        fetcher = CoverFetcher()
        pairs = fetcher.fetch_random_pairs(pair_count=1)
        if not pairs:
            raise RuntimeError("No book cover pairs could be fetched from any source.")

        cover_a, cover_b = pairs[0]
        logger.info(
            "Research: '%s' vs '%s'", cover_a.title[:40], cover_b.title[:40]
        )

        path_a = download_cover_image(cover_a.cover_url)
        path_b = download_cover_image(cover_b.cover_url)
        logger.debug("Cover A -> %s", path_a)
        logger.debug("Cover B -> %s", path_b)

        return ContestData(
            title=f"Which cover do you prefer? {cover_a.title}",
            description=(
                f'Compare two book cover designs. '
                f'"{cover_a.title}" by {cover_a.author} '
                f'vs "{cover_b.title}" by {cover_b.author}.'
            ),
            image_a_label=f"{cover_a.title[:30]} (A)",
            image_b_label=f"{cover_b.title[:30]} (B)",
            image_a_path=path_a,
            image_b_path=path_b,
            tags=", ".join(filter(None, [
                cover_a.author,
                "book cover",
                "design",
            ])),
        )

    # ------------------------------------------------------------------
    # Browser phase
    # ------------------------------------------------------------------

    async def _browser_phase(self, user: SimUser, data: ContestData) -> bool:
        """Execute all browser steps for *user* using *data*.

        :param SimUser user: Credentials and context key for this run.
        :param ContestData data: Pre-fetched form values and image paths.
        :returns: ``True`` on success.
        :rtype: bool
        """
        p = self.platform
        bm = self.bm

        await bm.switch_user(user.username)

        if not await self._login(user):
            return False

        result = await bm.navigate(p.create_route)
        if is_failure_result(result):
            logger.error("[%s] Navigate to create form failed: %s", user.display_name, result)
            return False

        # Fill text fields in declaration order.
        text_steps: list[tuple[str, str]] = [
            (p.title_selector, data.title),
            (p.description_selector, data.description),
        ]
        if p.image_a_label_selector:
            text_steps.append((p.image_a_label_selector, data.image_a_label))
        if p.image_b_label_selector:
            text_steps.append((p.image_b_label_selector, data.image_b_label))
        if p.tags_selector:
            text_steps.append((p.tags_selector, data.tags))

        for selector, value in text_steps:
            result = await bm.fill(selector, value)
            if is_failure_result(result):
                logger.error(
                    "[%s] Fill %r failed: %s", user.display_name, selector, result
                )
                return False

        # Upload cover images by index within all matching file inputs.
        if not await self._upload_covers(user, data):
            return False

        # Submit and verify redirect.
        result = await bm.click(p.submit_selector)
        if is_failure_result(result):
            logger.error("[%s] Submit click failed: %s", user.display_name, result)
            return False

        try:
            await bm.active_page.wait_for_url(
                lambda url: p.submit_success_excludes not in url,
                timeout=10000,
            )
        except Exception:
            logger.error(
                "[%s] Submission failed — still at %s",
                user.display_name, bm.active_page.url,
            )
            return False

        logger.info("[%s] Contest submitted successfully", user.display_name)
        await self._logout(user)
        return True

    async def _upload_covers(self, user: SimUser, data: ContestData) -> bool:
        """Upload cover-A and cover-B images to the nth file input elements.

        Addresses each ``<input type="file">`` by its position in the list of
        all elements matching ``platform.file_input_selector``.

        :param SimUser user: Used only for log context.
        :param ContestData data: Contains the local image paths to upload.
        :returns: ``True`` if both uploads succeeded.
        :rtype: bool
        """
        p = self.platform
        page = self.bm.active_page
        uploads = [
            (p.image_a_file_nth, data.image_a_path, "A"),
            (p.image_b_file_nth, data.image_b_path, "B"),
        ]
        for nth, path, label in uploads:
            try:
                inputs = await page.query_selector_all(p.file_input_selector)
                if nth >= len(inputs):
                    logger.error(
                        "[%s] Cover %s: expected file input[%d] but only %d found",
                        user.display_name, label, nth, len(inputs),
                    )
                    return False
                await inputs[nth].set_input_files(path)
                logger.debug(
                    "[%s] Cover %s uploaded to input[%d]", user.display_name, label, nth
                )
            except Exception as exc:
                logger.error(
                    "[%s] Cover %s upload failed: %s", user.display_name, label, exc
                )
                return False
        return True

    async def _login(self, user: SimUser) -> bool:
        """Navigate to login, fill credentials, and verify the redirect.

        :param SimUser user: Account to log in with.
        :returns: ``True`` if login succeeded.
        :rtype: bool
        """
        p = self.platform
        bm = self.bm

        result = await bm.navigate(p.login_route)
        if is_failure_result(result):
            logger.error("[%s] Login navigate failed: %s", user.display_name, result)
            return False

        for selector, value in [
            (p.email_selector, user.username),
            (p.password_selector, user.password),
        ]:
            result = await bm.fill(selector, value)
            if is_failure_result(result):
                logger.error(
                    "[%s] Login fill %r failed: %s", user.display_name, selector, result
                )
                return False

        result = await bm.click(p.login_submit_selector)
        if is_failure_result(result):
            logger.error("[%s] Login submit failed: %s", user.display_name, result)
            return False

        try:
            await bm.active_page.wait_for_url(
                lambda url: p.login_success_fragment in url,
                timeout=10000,
            )
        except Exception:
            logger.error(
                "[%s] Login failed — expected %r in URL, got %s",
                user.display_name, p.login_success_fragment, bm.active_page.url,
            )
            return False

        logger.info("[%s] Logged in", user.display_name)
        return True

    async def _logout(self, user: SimUser) -> None:
        """Attempt to log out.  Non-fatal on failure.

        Tries ``logout_selector`` first; falls back to ``logout_route``.

        :param SimUser user: Used only for log context.
        """
        p = self.platform
        try:
            if p.logout_selector:
                await self.bm.click(p.logout_selector)
            elif p.logout_route:
                await self.bm.navigate(p.logout_route)
            await self.bm.wait_for_page_ready()
            logger.info("[%s] Logged out", user.display_name)
        except Exception as exc:
            logger.warning("[%s] Logout step failed (non-fatal): %s", user.display_name, exc)


# ---------------------------------------------------------------------------
# Multi-user runner
# ---------------------------------------------------------------------------


async def run_multi_user_flow(
    bm: BrowserManager,
    n_users: int = 3,
    platform: PlatformConfig = THIS_OR_THAT,
    users: list[SimUser] | None = None,
) -> dict[str, bool]:
    """Run :class:`ContestCreationFlow` for *n_users* randomly selected users.

    Each user gets a fresh cover pair and runs the full flow independently.
    Results are collected and returned even when individual users fail, so a
    single failure does not abort the remaining runs.

    :param BrowserManager bm: An active :class:`~tot_agent.browser.BrowserManager`.
    :param int n_users: Number of users to run.  Capped at the pool size.
    :param PlatformConfig platform: Target platform configuration.
    :param list[SimUser] or None users: User pool override.  Defaults to
        :data:`~tot_agent.config.SIM_USERS`.
    :returns: Mapping of ``username -> success`` for every user that was run.
    :rtype: dict[str, bool]
    """
    pool = users or SIM_USERS
    chosen: list[SimUser] = random.sample(pool, k=min(n_users, len(pool)))
    logger.info(
        "Running contest flow for %d user(s): %s",
        len(chosen), [u.username for u in chosen],
    )
    flow = ContestCreationFlow(bm, platform=platform)
    results: dict[str, bool] = {}
    for user in chosen:
        results[user.username] = await flow.run_for_user(user)
    return results
