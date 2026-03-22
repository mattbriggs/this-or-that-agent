"""
tot_agent — Autonomous browser agent for scripted GUI testing.

This package provides a vision-capable AI agent that drives a real Playwright
browser to execute scripted test scenarios against web applications.  It was
initially built for the *This-or-That* A/B book-cover testing platform, but
the core components are generic enough to target any web GUI.

Typical usage::

    import asyncio
    from tot_agent.browser import BrowserManager
    from tot_agent.agent import BrowserAgent

    async def main():
        async with BrowserManager() as bm:
            agent = BrowserAgent(bm)
            result = await agent.run("Navigate to /login and verify the page loads.")
            print(result)

    asyncio.run(main())
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("tot-agent")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
