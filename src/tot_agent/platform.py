"""
platform.py — Platform configuration for the scripted contest-creation flow.

A PlatformConfig is a plain dataclass that declares the routes and CSS selectors
for a specific web application's login and contest-creation UI.  The flow in
flow.py is entirely generic — swap the PlatformConfig to target a different SaaS
platform without changing any other code.

See docs/adding-a-platform.md for a step-by-step authoring guide.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlatformConfig:
    """Declarative description of a platform's login and contest-creation UI.

    All ``*_selector`` fields accept standard CSS selectors understood by
    Playwright.  For forms where two elements share the same tag (e.g. two
    ``<input type="file">``) use ``file_input_selector`` with ``image_a_file_nth``
    and ``image_b_file_nth`` (0-based) to address the correct element by index.

    :param str name: Human-readable platform identifier used in log messages.

    Routes
    ------
    :param str login_route: Site-relative path to the login page.
    :param str dashboard_route: Site-relative path to the dashboard / home.
    :param str create_route: Site-relative path to the contest-creation form.

    Login form
    ----------
    :param str email_selector: CSS selector for the email / username field.
    :param str password_selector: CSS selector for the password field.
    :param str login_submit_selector: CSS selector for the login submit button.
    :param str login_success_fragment: Substring that must appear in the URL
        after a successful login (used to detect redirect failures).

    Contest creation form
    ---------------------
    :param str title_selector: CSS selector for the contest title field.
    :param str description_selector: CSS selector for the description textarea.
    :param str image_a_label_selector: CSS selector for the Image A edition label.
    :param str image_b_label_selector: CSS selector for the Image B edition label.
    :param str file_input_selector: Base CSS selector shared by both file inputs.
    :param int image_a_file_nth: 0-based index into ``file_input_selector`` matches
        for the Image A upload element.
    :param int image_b_file_nth: 0-based index into ``file_input_selector`` matches
        for the Image B upload element.
    :param str or None tags_selector: CSS selector for the tags / keywords field.
        Set to ``None`` if the platform has no tag field.
    :param str submit_selector: CSS selector for the form submit button.
    :param str submit_success_excludes: Substring that must NOT appear in the URL
        after a successful submission (used to detect a failed redirect).

    Logout
    ------
    :param str or None logout_selector: CSS selector (or visible text) for the
        logout link or button.  Takes precedence over ``logout_route``.
    :param str or None logout_route: Site-relative path to navigate to in order to
        log out.  Used only when ``logout_selector`` is ``None``.
    """

    name: str

    # ── Routes ────────────────────────────────────────────────────────────────

    login_route: str = "/login"
    dashboard_route: str = "/dashboard"
    create_route: str = "/contests/create"

    # ── Login form ────────────────────────────────────────────────────────────

    email_selector: str = "input[type='email']"
    password_selector: str = "input[type='password']"
    login_submit_selector: str = "button[type='submit']"
    login_success_fragment: str = "dashboard"

    # ── Contest creation form ─────────────────────────────────────────────────

    title_selector: str = "input[placeholder='Dog vs Cat']"
    description_selector: str = "textarea"
    image_a_label_selector: str = ""
    image_b_label_selector: str = ""
    file_input_selector: str = "input[type='file']"
    image_a_file_nth: int = 0
    image_b_file_nth: int = 1
    tags_selector: str | None = None
    submit_selector: str = "button[type='submit']"
    submit_success_excludes: str = "create"

    # ── Logout ────────────────────────────────────────────────────────────────

    logout_selector: str | None = None
    logout_route: str | None = None


# ── Built-in platform configurations ──────────────────────────────────────────

THIS_OR_THAT = PlatformConfig(
    name="this-or-that",
    #
    # Routes
    login_route="/login",
    dashboard_route="/dashboard",
    create_route="/contests/create",
    #
    # Login form
    email_selector="#email",
    password_selector="#password",
    login_submit_selector="button[type='submit']",
    login_success_fragment="dashboard",
    #
    # Contest creation form
    # Inspect the live form at /contests/create and adjust these selectors if
    # the page is updated.  Run: tot-agent covers "fantasy" --verify to confirm
    # covers resolve before running the full flow.
    title_selector="input[placeholder='Dog vs Cat']",
    description_selector="textarea[placeholder='Optional description\u2026']",
    image_a_label_selector="#image_a_label",
    image_b_label_selector="#image_b_label",
    file_input_selector="input[type='file']",
    image_a_file_nth=0,  # matches #image_a
    image_b_file_nth=1,  # matches #image_b
    tags_selector="#tags",
    submit_selector="button[type='submit']",
    submit_success_excludes="contests/create",
    #
    # Logout button uses a JS onclick — match by the removeItem call it contains
    logout_selector="button[onclick*='removeItem']",
    logout_route=None,
)
