"""
tools.py — Tool schema definitions for the Claude API and the dispatcher
that maps tool names to concrete browser/cover actions.

Design notes
------------
* The agent uses screenshots + vision to navigate, so tool schemas are kept
  intentionally generic (no hardcoded selectors).
* Higher-level tools (``login``) provide structure; lower-level tools
  (``click``, ``fill``, ``screenshot``) allow the agent to recover from
  unexpected UI states.
* :func:`dispatch` is the single entry point for the agent loop — it routes
  a tool name to the appropriate :class:`~tot_agent.browser.BrowserManager`
  method or cover-fetching function.

Adding a new tool
-----------------
1. Append a tool-schema dict to :data:`TOOL_DEFINITIONS`.
2. Add a ``case "tool_name":`` branch in :func:`dispatch`.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tot_agent.config import PAGE_READY_TIMEOUT_MS
from tot_agent.results import failure_result, is_failure_result

if TYPE_CHECKING:
    from tot_agent.browser import BrowserManager

logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schemas (passed verbatim to Claude messages.create)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    # -- Vision / navigation -------------------------------------------------
    {
        "name": "screenshot",
        "description": (
            "Take a screenshot of the current browser page for the active user. "
            "Use this to inspect the UI state before deciding what to do next."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "navigate",
        "description": (
            "Navigate the active user's browser to a URL "
            "(absolute or site-relative path like '/login')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL or relative path to navigate to",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": (
            "Click an element on the page. "
            "Pass a CSS selector (e.g. 'button[type=submit]') or visible text "
            "(e.g. 'Sign in'). If a CSS selector fails, the agent tries text matching."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or visible text to click",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "fill",
        "description": "Clear and type a value into an input or textarea identified by CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field",
                },
                "value": {"type": "string", "description": "Value to type"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape') on the active page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key name to press"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "get_page_text",
        "description": (
            "Return the visible text content of the current page (up to 4000 chars). "
            "Useful for reading test listings, error messages, etc."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_page_url",
        "description": "Return the current URL of the active browser page.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "scroll_down",
        "description": "Scroll to the bottom of the current page.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "wait_for_element",
        "description": (
            "Wait up to 8 s for a CSS selector to appear — "
            "use after form submissions or page transitions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to wait for",
                },
            },
            "required": ["selector"],
        },
    },
    # -- User context --------------------------------------------------------
    {
        "name": "switch_user",
        "description": (
            "Switch the active browser context to a different simulated user. "
            "Each user has an isolated session. You must login after switching to a "
            "user that hasn't authenticated yet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username of the simulated user to switch to",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "login",
        "description": (
            "Log into the site using a username and password. "
            "Navigates to the login page, fills credentials, and submits. "
            "Take a screenshot afterward to confirm success."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["username", "password"],
        },
    },
    # -- Book covers ---------------------------------------------------------
    {
        "name": "fetch_book_covers",
        "description": (
            "Search for real book cover images from Open Library / Google Books. "
            "Returns a list of covers with title, author, and a direct image URL. "
            "Pass the cover_url to upload_cover_image when the form expects a file upload "
            "rather than a URL string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Genre, title, or author to search for",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of covers to return (default 4)",
                    "default": 4,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "upload_cover_image",
        "description": (
            "Download a book cover image from a URL and upload it as a file to a "
            "<input type='file'> element on the current page. "
            "Use this instead of pasting a URL into a text field when the form expects "
            "an actual file upload. The cover_url comes from fetch_book_covers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cover_url": {
                    "type": "string",
                    "description": "Direct URL of the cover image to download and upload",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the <input type='file'> element",
                },
            },
            "required": ["cover_url", "selector"],
        },
    },
]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


async def dispatch(
    tool_name: str,
    tool_input: dict[str, Any],
    bm: BrowserManager,
) -> Any:
    """Route a tool call from the agent to the correct implementation.

    :param str tool_name: Name of the tool as declared in :data:`TOOL_DEFINITIONS`.
    :param dict[str, Any] tool_input: Input parameters from the Claude tool-use block.
    :param BrowserManager bm: Active :class:`~tot_agent.browser.BrowserManager` instance.
    :returns: A plain Python value (``str``, ``list``, or ``dict``).  The
        caller is responsible for serialising it into an API message.
    :rtype: Any
    """
    from tot_agent.config import ROUTES
    from tot_agent.covers import fetch_book_covers as _fetch_covers

    logger.debug("Dispatching tool %r with input %s", tool_name, tool_input)

    try:
        match tool_name:

            # -- Vision / navigation -----------------------------------------
            case "screenshot":
                return {
                    "type": "screenshot",
                    "ok": True,
                    "message": "Captured screenshot of the active page",
                    "data": await bm.screenshot(),
                }

            case "navigate":
                return await bm.navigate(tool_input["url"])

            case "click":
                return await bm.click(tool_input["selector"])

            case "fill":
                return await bm.fill(tool_input["selector"], tool_input["value"])

            case "press_key":
                return await bm.press_key(tool_input["key"])

            case "get_page_text":
                return await bm.get_page_text()

            case "get_page_url":
                return await bm.get_page_url()

            case "scroll_down":
                return await bm.scroll_down()

            case "wait_for_element":
                return await bm.wait_for_selector(tool_input["selector"])

            # -- User context ------------------------------------------------
            case "switch_user":
                return await bm.switch_user(tool_input["username"])

            case "login":
                username = tool_input["username"]
                password = tool_input["password"]
                steps: list[dict[str, Any]] = []

                step_result = await bm.navigate(ROUTES["login"])
                steps.append({"step": "navigate", "result": step_result})
                if is_failure_result(step_result):
                    return failure_result(
                        "Login flow failed while navigating to the login page",
                        error=step_result.get("error"),
                        username=username,
                        failed_step="navigate",
                        steps=steps,
                    )

                step_result = await bm.fill(
                    "input[type='text'], input[type='email'], "
                    "input[name='username'], input[name='email']",
                    username,
                )
                steps.append({"step": "fill_username", "result": step_result})
                if is_failure_result(step_result):
                    return failure_result(
                        "Login flow failed while filling the username field",
                        error=step_result.get("error"),
                        username=username,
                        failed_step="fill_username",
                        steps=steps,
                    )

                step_result = await bm.fill("input[type='password']", password)
                steps.append({"step": "fill_password", "result": step_result})
                if is_failure_result(step_result):
                    return failure_result(
                        "Login flow failed while filling the password field",
                        error=step_result.get("error"),
                        username=username,
                        failed_step="fill_password",
                        steps=steps,
                    )

                step_result = await bm.press_key("Enter")
                steps.append({"step": "submit", "result": step_result})
                if is_failure_result(step_result):
                    return failure_result(
                        "Login flow failed while submitting credentials",
                        error=step_result.get("error"),
                        username=username,
                        failed_step="submit",
                        steps=steps,
                    )

                settle_result = await bm.wait_for_page_ready(timeout=PAGE_READY_TIMEOUT_MS)
                steps.append({"step": "wait_for_page_ready", "result": settle_result})

                logger.info("Login submitted for user %r", username)
                return {
                    "ok": True,
                    "message": (
                        f"Login submitted for {username}. Verification is still required "
                        "with a screenshot or page text."
                    ),
                    "data": {
                        "username": username,
                        "verification_required": True,
                        "steps": steps,
                    },
                }

            # -- Book covers -------------------------------------------------
            case "fetch_book_covers":
                covers = _fetch_covers(
                    query=tool_input["query"],
                    count=tool_input.get("count", 4),
                )
                return {
                    "ok": True,
                    "message": f"Fetched {len(covers)} book cover candidates",
                    "data": {
                        "query": tool_input["query"],
                        "count": len(covers),
                        "covers": [
                            {
                                "title": c.title,
                                "author": c.author,
                                "cover_url": c.cover_url,
                                "source": c.source,
                            }
                            for c in covers
                        ],
                    },
                }

            case "upload_cover_image":
                import os

                from tot_agent.covers import download_cover_image

                tmp_path = download_cover_image(tool_input["cover_url"])
                try:
                    result = await bm.upload_file(tool_input["selector"], tmp_path)
                finally:
                    os.unlink(tmp_path)
                return result

            case _:
                logger.error("Unknown tool requested: %r", tool_name)
                return failure_result(
                    f"Unknown tool '{tool_name}'",
                    tool=tool_name,
                    tool_input=tool_input,
                )
    except KeyError as exc:
        logger.warning("Tool input missing required field for %r: %s", tool_name, exc)
        return failure_result(
            f"Tool '{tool_name}' is missing required input",
            error=str(exc),
            tool=tool_name,
            tool_input=tool_input,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Tool %r failed unexpectedly", tool_name)
        return failure_result(
            f"Tool '{tool_name}' failed unexpectedly",
            error=str(exc),
            tool=tool_name,
            tool_input=tool_input,
        )


# ---------------------------------------------------------------------------
# Tool result formatting
# ---------------------------------------------------------------------------


def format_tool_result(tool_use_id: str, result: Any) -> dict:
    """Package a tool result for the Anthropic messages API.

    Screenshots are sent as ``image`` content blocks; all other results are
    serialised to a text string.

    :param str tool_use_id: The ``id`` from the tool-use block in the API response.
    :param Any result: Raw return value from :func:`dispatch`.
    :returns: A ``tool_result`` dict ready to append to the messages list.
    :rtype: dict
    """
    if isinstance(result, dict) and result.get("type") == "screenshot":
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result["data"],
                    },
                }
            ],
        }

    if isinstance(result, (dict, list)):
        text = json.dumps(result, indent=2)
    else:
        text = str(result)

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": text,
    }
