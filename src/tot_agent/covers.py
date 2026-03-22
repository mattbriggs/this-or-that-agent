"""
covers.py — Book cover fetching via the Strategy design pattern.

Two concrete sources are provided out of the box:

* :class:`OpenLibrarySource` — primary source, free, no API key required.
* :class:`GoogleBooksSource` — fallback source, no API key required for
  low-volume requests.

The :class:`CoverFetcher` orchestrator accepts any list of
:class:`CoverSource` implementations, making it straightforward to add new
sources (e.g. Amazon, Goodreads) without touching existing code.

Example::

    from tot_agent.covers import CoverFetcher

    fetcher = CoverFetcher()
    covers = fetcher.fetch("fantasy epic", count=4)
    for cover in covers:
        print(cover)
"""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from tot_agent.config import (
    COVER_SEARCH_QUERIES,
    GOOGLE_BOOKS_URL,
    OPEN_LIBRARY_COVER_URL,
    OPEN_LIBRARY_SEARCH_URL,
)

logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass
class BookCover:
    """Metadata and image URL for a single book cover.

    :param title: Book title.
    :type title: str
    :param author: Primary author name.
    :type author: str
    :param cover_url: Direct URL to the cover image (HTTPS).
    :type cover_url: str
    :param source: Originating data source identifier (e.g. ``"openlibrary"``).
    :type source: str
    :param isbn: ISBN-10 or ISBN-13, if available.
    :type isbn: str or None
    """

    title: str
    author: str
    cover_url: str
    source: str
    isbn: Optional[str] = None

    def __str__(self) -> str:
        return f'"{self.title}" by {self.author} — {self.cover_url}'

    def __repr__(self) -> str:
        return (
            f"BookCover(title={self.title!r}, author={self.author!r}, "
            f"source={self.source!r})"
        )


# ---------------------------------------------------------------------------
# Strategy interface
# ---------------------------------------------------------------------------


class CoverSource(ABC):
    """Abstract base class for book cover data sources (Strategy pattern).

    Subclasses implement :meth:`search` to query a specific upstream API and
    return a normalised list of :class:`BookCover` objects.
    """

    @abstractmethod
    def search(self, query: str, limit: int) -> list[BookCover]:
        """Search for book covers matching *query*.

        :param query: Free-text search query (title, author, or genre).
        :type query: str
        :param limit: Maximum number of results to return.
        :type limit: int
        :returns: List of matching book covers (may be empty).
        :rtype: list[BookCover]
        """


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------


class OpenLibrarySource(CoverSource):
    """Fetch book covers from the Open Library search API.

    This is the primary source.  No API key is required.

    :param timeout: HTTP request timeout in seconds.  Defaults to ``10``.
    :type timeout: int
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    def search(self, query: str, limit: int) -> list[BookCover]:
        """Search Open Library and return books that have cover images.

        :param query: Search query string.
        :type query: str
        :param limit: Maximum number of covers to return.
        :type limit: int
        :returns: List of :class:`BookCover` objects with Open Library image URLs.
        :rtype: list[BookCover]
        """
        covers: list[BookCover] = []
        try:
            resp = httpx.get(
                OPEN_LIBRARY_SEARCH_URL,
                params={
                    "q": query,
                    "limit": limit,
                    "fields": "title,author_name,cover_i,isbn",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            docs = resp.json().get("docs", [])

            for doc in docs:
                cover_id = doc.get("cover_i")
                if not cover_id:
                    continue
                title = doc.get("title", "Unknown Title")
                authors = doc.get("author_name", ["Unknown Author"])
                author = authors[0] if authors else "Unknown Author"
                isbn_list = doc.get("isbn", [])
                isbn: Optional[str] = isbn_list[0] if isbn_list else None
                url = OPEN_LIBRARY_COVER_URL.format(cover_id=cover_id)
                covers.append(
                    BookCover(
                        title=title,
                        author=author,
                        cover_url=url,
                        source="openlibrary",
                        isbn=isbn,
                    )
                )
            logger.debug(
                "OpenLibrary returned %d covers for query %r", len(covers), query
            )
        except httpx.HTTPError as exc:
            logger.warning("Open Library search failed: %s", exc)
        return covers


class GoogleBooksSource(CoverSource):
    """Fetch book covers from the Google Books API (fallback source).

    No API key is required for low-volume requests.

    :param timeout: HTTP request timeout in seconds.  Defaults to ``10``.
    :type timeout: int
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    def search(self, query: str, limit: int) -> list[BookCover]:
        """Search the Google Books API and return books that have cover images.

        :param query: Search query string.
        :type query: str
        :param limit: Maximum number of covers to return.
        :type limit: int
        :returns: List of :class:`BookCover` objects with Google Books image URLs.
        :rtype: list[BookCover]
        """
        covers: list[BookCover] = []
        try:
            resp = httpx.get(
                GOOGLE_BOOKS_URL,
                params={
                    "q": query,
                    "maxResults": min(limit, 40),
                    "printType": "books",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            for item in items:
                info = item.get("volumeInfo", {})
                image_links = info.get("imageLinks", {})
                cover_url: Optional[str] = (
                    image_links.get("extraLarge")
                    or image_links.get("large")
                    or image_links.get("medium")
                    or image_links.get("thumbnail")
                )
                if not cover_url:
                    continue
                cover_url = cover_url.replace("http://", "https://")
                title = info.get("title", "Unknown Title")
                authors = info.get("authors", ["Unknown Author"])
                author = authors[0] if authors else "Unknown Author"
                covers.append(
                    BookCover(
                        title=title,
                        author=author,
                        cover_url=cover_url,
                        source="googlebooks",
                    )
                )
            logger.debug(
                "GoogleBooks returned %d covers for query %r", len(covers), query
            )
        except httpx.HTTPError as exc:
            logger.warning("Google Books search failed: %s", exc)
        return covers


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class CoverFetcher:
    """Orchestrates cover fetching across one or more :class:`CoverSource` strategies.

    Sources are queried in order until *count* unique covers have been gathered.
    Results are deduplicated by normalised title.

    :param sources: Ordered list of sources to query.  Defaults to
        ``[OpenLibrarySource(), GoogleBooksSource()]``.
    :type sources: list[CoverSource] or None

    Example::

        fetcher = CoverFetcher()
        covers = fetcher.fetch("mystery thriller", count=3)
    """

    def __init__(self, sources: Optional[list[CoverSource]] = None) -> None:
        self._sources: list[CoverSource] = sources or [
            OpenLibrarySource(),
            GoogleBooksSource(),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, query: str, count: int = 5) -> list[BookCover]:
        """Fetch *count* book covers matching *query*.

        Tries each configured source in order, deduplicates by title, and
        returns up to *count* results.

        :param query: Free-text search query.
        :type query: str
        :param count: Number of covers to return.
        :type count: int
        :returns: List of unique :class:`BookCover` objects (length <= *count*).
        :rtype: list[BookCover]
        """
        logger.info("Fetching %d covers for query %r", count, query)
        pool: list[BookCover] = []

        for source in self._sources:
            if len(pool) >= count:
                break
            needed = (count - len(pool)) * 3
            pool.extend(source.search(query, limit=needed))

        unique = self._deduplicate(pool)
        selected = unique[:count]

        if not selected:
            logger.warning("No covers found for query %r", query)
        else:
            logger.info("Selected %d cover(s) for %r", len(selected), query)

        return selected

    def fetch_random_pairs(
        self, pair_count: int = 5
    ) -> list[tuple[BookCover, BookCover]]:
        """Return *pair_count* pairs of ``(cover_a, cover_b)`` from random genres.

        Useful for seeding A/B tests without repetition within a pair.

        :param pair_count: Number of cover pairs to generate.
        :type pair_count: int
        :returns: List of 2-tuples, each containing two distinct
            :class:`BookCover` objects.
        :rtype: list[tuple[BookCover, BookCover]]
        """
        queries = random.sample(
            COVER_SEARCH_QUERIES, k=min(pair_count, len(COVER_SEARCH_QUERIES))
        )
        pairs: list[tuple[BookCover, BookCover]] = []
        for query in queries:
            covers = self.fetch(query, count=2)
            if len(covers) >= 2:
                pairs.append((covers[0], covers[1]))
            if len(pairs) >= pair_count:
                break
        logger.info("Generated %d cover pair(s)", len(pairs))
        return pairs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate(covers: list[BookCover]) -> list[BookCover]:
        """Remove covers with duplicate normalised titles.

        :param covers: Raw list possibly containing duplicates.
        :type covers: list[BookCover]
        :returns: Deduplicated list preserving original order.
        :rtype: list[BookCover]
        """
        seen: set[str] = set()
        unique: list[BookCover] = []
        for cover in covers:
            key = cover.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(cover)
        return unique


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def verify_cover_url(url: str, timeout: int = 5) -> bool:
    """Perform a HEAD request to verify that *url* resolves to a live image.

    :param url: The image URL to check.
    :type url: str
    :param timeout: HTTP timeout in seconds.  Defaults to ``5``.
    :type timeout: int
    :returns: ``True`` if the URL returns HTTP 200, ``False`` otherwise.
    :rtype: bool
    """
    try:
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        return resp.status_code == 200
    except httpx.HTTPError as exc:
        logger.debug("Cover URL check failed for %s: %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# Module-level convenience instance (mirrors original public API)
# ---------------------------------------------------------------------------

_default_fetcher: CoverFetcher = CoverFetcher()


def fetch_book_covers(query: str, count: int = 5) -> list[BookCover]:
    """Module-level convenience wrapper around :class:`CoverFetcher`.

    :param query: Search query.
    :type query: str
    :param count: Number of covers to fetch.
    :type count: int
    :returns: List of :class:`BookCover` objects.
    :rtype: list[BookCover]
    """
    return _default_fetcher.fetch(query, count=count)


def fetch_random_cover_pairs(pair_count: int = 5) -> list[tuple[BookCover, BookCover]]:
    """Module-level convenience wrapper for random cover pairs.

    :param pair_count: Number of pairs to generate.
    :type pair_count: int
    :returns: List of ``(cover_a, cover_b)`` tuples.
    :rtype: list[tuple[BookCover, BookCover]]
    """
    return _default_fetcher.fetch_random_pairs(pair_count=pair_count)
