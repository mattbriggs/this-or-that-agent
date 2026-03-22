"""
tests/unit/test_covers.py — Unit tests for tot_agent.covers.

All external HTTP calls are intercepted with :mod:`respx` (HTTPX mock library)
so tests run offline without hitting real APIs.
"""

from __future__ import annotations

import json
import pytest
import respx
import httpx


# ---------------------------------------------------------------------------
# BookCover dataclass
# ---------------------------------------------------------------------------


class TestBookCover:
    def test_str_representation(self):
        from tot_agent.covers import BookCover
        c = BookCover(title="Dune", author="Frank Herbert",
                      cover_url="https://example.com/dune.jpg", source="openlibrary")
        s = str(c)
        assert "Dune" in s
        assert "Frank Herbert" in s
        assert "https://example.com/dune.jpg" in s

    def test_repr_contains_key_fields(self):
        from tot_agent.covers import BookCover
        c = BookCover(title="Dune", author="Frank Herbert",
                      cover_url="https://example.com/dune.jpg", source="openlibrary")
        r = repr(c)
        assert "BookCover" in r
        assert "openlibrary" in r

    def test_isbn_defaults_to_none(self):
        from tot_agent.covers import BookCover
        c = BookCover("T", "A", "http://x.com/img.jpg", "test")
        assert c.isbn is None


# ---------------------------------------------------------------------------
# OpenLibrarySource
# ---------------------------------------------------------------------------


class TestOpenLibrarySource:
    @respx.mock
    def test_returns_covers_with_cover_id(self, open_library_response):
        from tot_agent.covers import OpenLibrarySource
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json=open_library_response)
        )
        source = OpenLibrarySource()
        covers = source.search("science fiction", limit=10)
        # Two of the three docs have cover_i
        assert len(covers) == 2
        assert covers[0].title == "Dune"
        assert covers[0].source == "openlibrary"
        assert covers[0].isbn == "9780441013593"
        assert "12345" in covers[0].cover_url

    @respx.mock
    def test_skips_docs_without_cover_id(self, open_library_response):
        from tot_agent.covers import OpenLibrarySource
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json=open_library_response)
        )
        source = OpenLibrarySource()
        covers = source.search("anything", limit=10)
        titles = [c.title for c in covers]
        assert "No Cover Book" not in titles

    @respx.mock
    def test_returns_empty_on_http_error(self):
        from tot_agent.covers import OpenLibrarySource
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(500)
        )
        source = OpenLibrarySource()
        covers = source.search("anything", limit=5)
        assert covers == []

    @respx.mock
    def test_handles_missing_author_gracefully(self):
        from tot_agent.covers import OpenLibrarySource
        payload = {
            "docs": [{"title": "Orphan Book", "cover_i": 999, "author_name": []}]
        }
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json=payload)
        )
        source = OpenLibrarySource()
        covers = source.search("orphan", limit=5)
        assert len(covers) == 1
        assert covers[0].author == "Unknown Author"


# ---------------------------------------------------------------------------
# GoogleBooksSource
# ---------------------------------------------------------------------------


class TestGoogleBooksSource:
    @respx.mock
    def test_returns_covers_with_image_links(self, google_books_response):
        from tot_agent.covers import GoogleBooksSource
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=google_books_response)
        )
        source = GoogleBooksSource()
        covers = source.search("cyberpunk", limit=5)
        assert len(covers) == 1
        assert covers[0].title == "Neuromancer"
        assert covers[0].source == "googlebooks"
        # http -> https upgrade
        assert covers[0].cover_url.startswith("https://")

    @respx.mock
    def test_skips_items_without_image_links(self, google_books_response):
        from tot_agent.covers import GoogleBooksSource
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=google_books_response)
        )
        source = GoogleBooksSource()
        covers = source.search("anything", limit=10)
        titles = [c.title for c in covers]
        assert "No Image Book" not in titles

    @respx.mock
    def test_returns_empty_on_http_error(self):
        from tot_agent.covers import GoogleBooksSource
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(503)
        )
        source = GoogleBooksSource()
        covers = source.search("anything", limit=5)
        assert covers == []

    @respx.mock
    def test_upgrades_http_to_https(self):
        from tot_agent.covers import GoogleBooksSource
        payload = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "HTTP Book",
                        "authors": ["Author"],
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/cover.jpg"
                        },
                    }
                }
            ]
        }
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=payload)
        )
        source = GoogleBooksSource()
        covers = source.search("anything", limit=5)
        assert covers[0].cover_url.startswith("https://")


# ---------------------------------------------------------------------------
# CoverFetcher (orchestrator)
# ---------------------------------------------------------------------------


class TestCoverFetcher:
    def test_deduplicates_by_title(self):
        from tot_agent.covers import CoverFetcher, BookCover, CoverSource

        class DuplicateSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover("Dune", "A", "http://x.com/1.jpg", "test"),
                    BookCover("dune", "B", "http://x.com/2.jpg", "test"),  # duplicate (normalised)
                    BookCover("Foundation", "C", "http://x.com/3.jpg", "test"),
                ]

        fetcher = CoverFetcher(sources=[DuplicateSource()])
        covers = fetcher.fetch("anything", count=10)
        titles = [c.title for c in covers]
        assert len(titles) == len(set(t.lower() for t in titles))

    def test_limits_results_to_count(self):
        from tot_agent.covers import CoverFetcher, BookCover, CoverSource

        class BigSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover(f"Book {i}", "A", f"http://x.com/{i}.jpg", "test")
                    for i in range(20)
                ]

        fetcher = CoverFetcher(sources=[BigSource()])
        covers = fetcher.fetch("anything", count=5)
        assert len(covers) == 5

    def test_falls_back_to_second_source(self):
        from tot_agent.covers import CoverFetcher, BookCover, CoverSource

        class EmptySource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return []

        class FallbackSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [BookCover("Fallback Book", "A", "http://x.com/fb.jpg", "fallback")]

        fetcher = CoverFetcher(sources=[EmptySource(), FallbackSource()])
        covers = fetcher.fetch("anything", count=1)
        assert len(covers) == 1
        assert covers[0].title == "Fallback Book"

    def test_returns_empty_when_all_sources_fail(self):
        from tot_agent.covers import CoverFetcher, CoverSource, BookCover

        class EmptySource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return []

        fetcher = CoverFetcher(sources=[EmptySource()])
        covers = fetcher.fetch("anything", count=3)
        assert covers == []

    def test_fetch_random_pairs_returns_pairs(self):
        from tot_agent.covers import CoverFetcher, BookCover, CoverSource

        class PairSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover(f"Book A {query}", "X", f"http://x.com/a.jpg", "test"),
                    BookCover(f"Book B {query}", "Y", f"http://x.com/b.jpg", "test"),
                ]

        fetcher = CoverFetcher(sources=[PairSource()])
        pairs = fetcher.fetch_random_pairs(pair_count=2)
        assert len(pairs) == 2
        for a, b in pairs:
            assert a.title != b.title


# ---------------------------------------------------------------------------
# verify_cover_url
# ---------------------------------------------------------------------------


class TestVerifyCoverUrl:
    @respx.mock
    def test_returns_true_for_200(self):
        from tot_agent.covers import verify_cover_url
        url = "https://covers.openlibrary.org/b/id/12345-L.jpg"
        respx.head(url).mock(return_value=httpx.Response(200))
        assert verify_cover_url(url) is True

    @respx.mock
    def test_returns_false_for_404(self):
        from tot_agent.covers import verify_cover_url
        url = "https://covers.openlibrary.org/b/id/99999-L.jpg"
        respx.head(url).mock(return_value=httpx.Response(404))
        assert verify_cover_url(url) is False

    @respx.mock
    def test_returns_false_on_connection_error(self):
        from tot_agent.covers import verify_cover_url
        url = "https://covers.openlibrary.org/b/id/00000-L.jpg"
        respx.head(url).mock(side_effect=httpx.ConnectError("failed"))
        assert verify_cover_url(url) is False
