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

## Module reference

::: tot_agent.covers
    options:
      members:
        - BookCover
        - CoverSource
        - OpenLibrarySource
        - GoogleBooksSource
        - CoverFetcher
        - verify_cover_url
        - fetch_book_covers
        - fetch_random_cover_pairs
