# tot_agent.covers

Book cover fetching with the Strategy design pattern.

## Class diagram

```mermaid
classDiagram
    class CoverSource {
        <<abstract>>
        +search(query: str, limit: int) list~BookCover~
    }
    class OpenLibrarySource {
        -_timeout: int
        +search(query, limit) list~BookCover~
    }
    class GoogleBooksSource {
        -_timeout: int
        +search(query, limit) list~BookCover~
    }
    class CoverFetcher {
        -_sources: list~CoverSource~
        +fetch(query, count) list~BookCover~
        +fetch_random_pairs(pair_count) list
        -_deduplicate(covers) list~BookCover~
    }
    class BookCover {
        +title: str
        +author: str
        +cover_url: str
        +source: str
        +isbn: str
    }
    CoverSource <|-- OpenLibrarySource
    CoverSource <|-- GoogleBooksSource
    CoverFetcher --> CoverSource : uses
    CoverFetcher ..> BookCover : produces
```

## Fetch flow

```mermaid
flowchart TD
    A[fetch query, count] --> B{OpenLibrary has enough?}
    B -- yes --> D[deduplicate]
    B -- no --> C[GoogleBooks fallback]
    C --> D
    D --> E[truncate to count]
    E --> F[return BookCover list]
```

## Image download

`download_cover_image(url)` downloads a cover image to a local temp file and
returns the path.  The caller is responsible for deleting the file after use.

```mermaid
flowchart LR
    A["download_cover_image(url)"] --> B["httpx.get(url)"]
    B --> C{status ok?}
    C -- no --> D["raise HTTPStatusError"]
    C -- yes --> E["inspect Content-Type"]
    E --> F["tempfile.mkstemp(suffix=ext)"]
    F --> G["write bytes"]
    G --> H["return path"]
```

The extension is derived from the `Content-Type` response header:

| Content-Type | Extension |
|---|---|
| `image/jpeg` | `.jpg` |
| `image/png` | `.png` |
| `image/gif` | `.gif` |
| `image/webp` | `.webp` |
| `image/bmp` | `.bmp` |
| *(other)* | `.jpg` |

## Module reference

::: tot_agent.covers
    options:
      members:
        - BookCover
        - CoverSource
        - OpenLibrarySource
        - GoogleBooksSource
        - CoverFetcher
        - download_cover_image
        - verify_cover_url
        - fetch_book_covers
        - fetch_random_cover_pairs
