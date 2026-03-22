"""
tests/unit/test_covers.py — Unit tests for tot_agent.covers.

All external HTTP calls are patched at the :mod:`httpx` call site so tests run
offline without hitting real APIs.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest


def make_response(
    method: str,
    url: str,
    status_code: int,
    *,
    json_data: dict | None = None,
) -> httpx.Response:
    """Build an HTTPX response with an attached request for raise_for_status()."""
    request = httpx.Request(method, url)
    return httpx.Response(status_code, json=json_data, request=request)


# ---------------------------------------------------------------------------
# BookCover dataclass
# ---------------------------------------------------------------------------


class TestBookCover:
    def test_str_representation(self):
        from tot_agent.covers import BookCover

        cover = BookCover(
            title="Dune",
            author="Frank Herbert",
            cover_url="https://example.com/dune.jpg",
            source="openlibrary",
        )
        rendered = str(cover)
        assert "Dune" in rendered
        assert "Frank Herbert" in rendered
        assert "https://example.com/dune.jpg" in rendered

    def test_repr_contains_key_fields(self):
        from tot_agent.covers import BookCover

        cover = BookCover(
            title="Dune",
            author="Frank Herbert",
            cover_url="https://example.com/dune.jpg",
            source="openlibrary",
        )
        rendered = repr(cover)
        assert "BookCover" in rendered
        assert "openlibrary" in rendered

    def test_isbn_defaults_to_none(self):
        from tot_agent.covers import BookCover

        cover = BookCover("T", "A", "http://x.com/img.jpg", "test")
        assert cover.isbn is None


# ---------------------------------------------------------------------------
# OpenLibrarySource
# ---------------------------------------------------------------------------


class TestOpenLibrarySource:
    def test_returns_covers_with_cover_id(self, open_library_response):
        from tot_agent.covers import OpenLibrarySource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://openlibrary.org/search.json",
                200,
                json_data=open_library_response,
            ),
        ):
            source = OpenLibrarySource()
            covers = source.search("science fiction", limit=10)

        assert len(covers) == 2
        assert covers[0].title == "Dune"
        assert covers[0].source == "openlibrary"
        assert covers[0].isbn == "9780441013593"
        assert "12345" in covers[0].cover_url

    def test_skips_docs_without_cover_id(self, open_library_response):
        from tot_agent.covers import OpenLibrarySource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://openlibrary.org/search.json",
                200,
                json_data=open_library_response,
            ),
        ):
            source = OpenLibrarySource()
            covers = source.search("anything", limit=10)

        titles = [cover.title for cover in covers]
        assert "No Cover Book" not in titles

    def test_returns_empty_on_http_error(self):
        from tot_agent.covers import OpenLibrarySource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://openlibrary.org/search.json",
                500,
            ),
        ):
            source = OpenLibrarySource()
            covers = source.search("anything", limit=5)

        assert covers == []

    def test_handles_missing_author_gracefully(self):
        from tot_agent.covers import OpenLibrarySource

        payload = {
            "docs": [{"title": "Orphan Book", "cover_i": 999, "author_name": []}]
        }
        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://openlibrary.org/search.json",
                200,
                json_data=payload,
            ),
        ):
            source = OpenLibrarySource()
            covers = source.search("orphan", limit=5)

        assert len(covers) == 1
        assert covers[0].author == "Unknown Author"


# ---------------------------------------------------------------------------
# GoogleBooksSource
# ---------------------------------------------------------------------------


class TestGoogleBooksSource:
    def test_returns_covers_with_image_links(self, google_books_response):
        from tot_agent.covers import GoogleBooksSource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://www.googleapis.com/books/v1/volumes",
                200,
                json_data=google_books_response,
            ),
        ):
            source = GoogleBooksSource()
            covers = source.search("cyberpunk", limit=5)

        assert len(covers) == 1
        assert covers[0].title == "Neuromancer"
        assert covers[0].source == "googlebooks"
        assert covers[0].cover_url.startswith("https://")

    def test_skips_items_without_image_links(self, google_books_response):
        from tot_agent.covers import GoogleBooksSource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://www.googleapis.com/books/v1/volumes",
                200,
                json_data=google_books_response,
            ),
        ):
            source = GoogleBooksSource()
            covers = source.search("anything", limit=10)

        titles = [cover.title for cover in covers]
        assert "No Image Book" not in titles

    def test_returns_empty_on_http_error(self):
        from tot_agent.covers import GoogleBooksSource

        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://www.googleapis.com/books/v1/volumes",
                503,
            ),
        ):
            source = GoogleBooksSource()
            covers = source.search("anything", limit=5)

        assert covers == []

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
        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_response(
                "GET",
                "https://www.googleapis.com/books/v1/volumes",
                200,
                json_data=payload,
            ),
        ):
            source = GoogleBooksSource()
            covers = source.search("anything", limit=5)

        assert covers[0].cover_url.startswith("https://")


# ---------------------------------------------------------------------------
# CoverFetcher (orchestrator)
# ---------------------------------------------------------------------------


class TestCoverFetcher:
    def test_deduplicates_by_title(self):
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

        class DuplicateSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover("Dune", "A", "http://x.com/1.jpg", "test"),
                    BookCover("dune", "B", "http://x.com/2.jpg", "test"),
                    BookCover("Foundation", "C", "http://x.com/3.jpg", "test"),
                ]

        fetcher = CoverFetcher(sources=[DuplicateSource()])
        covers = fetcher.fetch("anything", count=10)
        titles = [cover.title for cover in covers]
        assert len(titles) == len({title.lower() for title in titles})

    def test_limits_results_to_count(self):
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

        class BigSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover(f"Book {index}", "A", f"http://x.com/{index}.jpg", "test")
                    for index in range(20)
                ]

        fetcher = CoverFetcher(sources=[BigSource()])
        covers = fetcher.fetch("anything", count=5)
        assert len(covers) == 5

    def test_falls_back_to_second_source(self):
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

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
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

        class EmptySource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return []

        fetcher = CoverFetcher(sources=[EmptySource()])
        covers = fetcher.fetch("anything", count=3)
        assert covers == []

    def test_fetch_random_pairs_returns_pairs(self):
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

        class PairSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                return [
                    BookCover(f"Book A {query}", "X", "http://x.com/a.jpg", "test"),
                    BookCover(f"Book B {query}", "Y", "http://x.com/b.jpg", "test"),
                ]

        fetcher = CoverFetcher(sources=[PairSource()])
        pairs = fetcher.fetch_random_pairs(pair_count=2)
        assert len(pairs) == 2
        for left, right in pairs:
            assert left.title != right.title

    def test_fetch_breaks_early_when_count_satisfied_by_first_source(self):
        """Line 275: the `break` inside the sources loop is hit when the pool
        is already full before the second source is queried."""
        from tot_agent.covers import BookCover, CoverFetcher, CoverSource

        call_counts: dict[str, int] = {"first": 0, "second": 0}

        class FirstSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                call_counts["first"] += 1
                return [
                    BookCover(f"Book {i}", "Author", f"https://x.com/{i}.jpg", "test")
                    for i in range(limit)
                ]

        class SecondSource(CoverSource):
            def search(self, query: str, limit: int) -> list[BookCover]:
                call_counts["second"] += 1
                return []

        fetcher = CoverFetcher(sources=[FirstSource(), SecondSource()])
        covers = fetcher.fetch("any", count=2)
        assert len(covers) == 2
        assert call_counts["first"] == 1
        assert call_counts["second"] == 0  # never reached — break fired


# ---------------------------------------------------------------------------
# download_cover_image
# ---------------------------------------------------------------------------


def make_image_response(url: str, content: bytes, content_type: str) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        200,
        content=content,
        headers={"content-type": content_type},
        request=request,
    )


class TestDownloadCoverImage:
    def test_writes_jpeg_to_temp_file(self):
        import os

        from tot_agent.covers import download_cover_image

        fake_bytes = b"\xff\xd8\xff" + b"\x00" * 100
        url = "https://example.com/cover.jpg"
        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_image_response(url, fake_bytes, "image/jpeg"),
        ):
            path = download_cover_image(url)

        try:
            assert os.path.exists(path)
            assert path.endswith(".jpg")
            assert open(path, "rb").read() == fake_bytes
        finally:
            os.unlink(path)

    def test_uses_png_extension_for_png_content_type(self):
        import os

        from tot_agent.covers import download_cover_image

        url = "https://example.com/cover.png"
        with patch(
            "tot_agent.covers.httpx.get",
            return_value=make_image_response(url, b"\x89PNG", "image/png"),
        ):
            path = download_cover_image(url)

        try:
            assert path.endswith(".png")
        finally:
            os.unlink(path)

    def test_raises_on_http_error(self):
        from tot_agent.covers import download_cover_image

        request = httpx.Request("GET", "https://example.com/missing.jpg")
        bad_response = httpx.Response(404, request=request)
        with patch("tot_agent.covers.httpx.get", return_value=bad_response):
            with pytest.raises(httpx.HTTPStatusError):
                download_cover_image("https://example.com/missing.jpg")


# ---------------------------------------------------------------------------
# Module-level wrappers
# ---------------------------------------------------------------------------


class TestModuleLevelWrappers:
    def test_fetch_book_covers_uses_default_fetcher(self):
        from tot_agent.covers import BookCover, fetch_book_covers

        fake_covers = [
            BookCover("Dune", "Frank Herbert", "https://img/dune.jpg", "openlibrary")
        ]
        with patch("tot_agent.covers._default_fetcher.fetch", return_value=fake_covers) as mock_fetch:
            result = fetch_book_covers("dune", count=1)
        mock_fetch.assert_called_once_with("dune", count=1)
        assert result == fake_covers

    def test_fetch_random_cover_pairs_uses_default_fetcher(self):
        from tot_agent.covers import BookCover, fetch_random_cover_pairs

        fake_pairs = [(
            BookCover("A", "Author A", "https://img/a.jpg", "openlibrary"),
            BookCover("B", "Author B", "https://img/b.jpg", "googlebooks"),
        )]
        with patch(
            "tot_agent.covers._default_fetcher.fetch_random_pairs",
            return_value=fake_pairs,
        ) as mock_fetch:
            result = fetch_random_cover_pairs(pair_count=1)
        mock_fetch.assert_called_once_with(pair_count=1)
        assert result == fake_pairs


# ---------------------------------------------------------------------------
# verify_cover_url
# ---------------------------------------------------------------------------


class TestVerifyCoverUrl:
    def test_returns_true_for_200(self):
        from tot_agent.covers import verify_cover_url

        url = "https://covers.openlibrary.org/b/id/12345-L.jpg"
        with patch(
            "tot_agent.covers.httpx.head",
            return_value=make_response("HEAD", url, 200),
        ):
            assert verify_cover_url(url) is True

    def test_returns_false_for_404(self):
        from tot_agent.covers import verify_cover_url

        url = "https://covers.openlibrary.org/b/id/99999-L.jpg"
        with patch(
            "tot_agent.covers.httpx.head",
            return_value=make_response("HEAD", url, 404),
        ):
            assert verify_cover_url(url) is False

    def test_returns_false_on_connection_error(self):
        from tot_agent.covers import verify_cover_url

        url = "https://covers.openlibrary.org/b/id/00000-L.jpg"
        with patch(
            "tot_agent.covers.httpx.head",
            side_effect=httpx.ConnectError("failed"),
        ):
            assert verify_cover_url(url) is False
