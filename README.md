# anime-scraper

CLI tool to search, group, and download anime torrents from [nyaa.si](https://nyaa.si).

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- Search nyaa.si with category and dub filters
- Deterministic grouping by release group, season, audio/subtitle language, and quality
- Interactive language preference selection (audio and subtitle)
- Download `.torrent` files and create magnet bundle text files
- Disk-based HTTP response caching (24h TTL) for faster repeated searches
- Rich terminal UI with progress bars and formatted tables

## Installation

```bash
# Install from source
pip install -e .

# With dev dependencies (pytest, coverage, respx)
pip install -e ".[dev]"
```

## Quick Start

```bash
# Search for an anime
anime-scraper search "Frieren"

# Search for dubbed content only
anime-scraper search "One Piece" --dub

# Search with more pages and custom output directory
anime-scraper search "Jujutsu Kaisen" --pages 10 --output ~/torrents

# List available categories
anime-scraper categories
```

## Commands Reference

### `search`

```
anime-scraper search <ANIME_NAME> [OPTIONS]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--dub` | `-d` | `False` | Filter for English dubbed content only |
| `--pages` | `-p` | `5` | Maximum number of search result pages to fetch |
| `--category` | `-c` | `anime_english` | Category: `all`, `anime`, `anime_english`, `anime_non_english`, `anime_raw` |
| `--output` | `-o` | `~/Downloads/anime-torrents` | Directory to save downloaded files |
| `--no-submitters` | | `False` | Skip fetching submitter info (faster but less accurate grouping) |

### `categories`

List all available nyaa.si categories and their codes.

### `version`

Show the version number.

## Interactive Workflow

When you run `anime-scraper search "Frieren"`, the tool walks through these steps:

1. **Search** -- Queries nyaa.si across up to N pages, optionally fetching submitter info from detail pages
2. **Language filter** -- Prompts you to select preferred audio and subtitle languages, then filters results
3. **Metadata extraction & grouping** -- Fetches detail pages, extracts metadata (release group, season, quality, etc.), and groups torrents by a deterministic key: `{release_group}|{anime_name}|{season}|{audio}|{subtitle}|{quality}`
4. **Group selection** -- Displays a table of groups with episode range, quality, seeder counts; you pick one to inspect
5. **Download** -- Asks whether to download `.torrent` files, create a magnet bundle, or both, then saves to the output directory

## Architecture

```
anime_scraper/
├── cli.py        -> Typer CLI entry point, interactive prompts, display logic
├── scraper.py    -> nyaa.si HTTP client, search/parse logic, builds Torrent objects
├── metadata.py   -> Fetches detail pages, extracts TorrentMetadata via regex
├── grouper.py    -> Deterministic grouping by metadata key
├── downloader.py -> Downloads .torrent files, creates magnet bundle text files
├── models.py     -> Dataclasses: Torrent, TorrentMetadata, TorrentGroup
├── cache.py      -> Disk-based HTTP response cache (SHA-256 hashed URLs)
└── utils.py      -> Shared Rich console, language keywords, helpers
```

**Data flow:**

```
search_nyaa() -> list[Torrent]
    -> fetch_metadata_for_torrents() -> populates torrent.metadata
    -> group_torrents_deterministic() -> list[TorrentGroup]
    -> create_combined_output() -> .torrent files + magnet bundle
```

## Configuration

| Setting | Location | Default |
|---|---|---|
| HTTP cache | `~/.cache/anime-scraper/` | 24-hour TTL |
| Download directory | `~/Downloads/anime-torrents/` | Overridable with `--output` |

## Development

```bash
# Run all tests with coverage
pytest

# Run by marker
pytest -m unit
pytest -m integration
pytest -m cli

# Run a single test
pytest -k "test_name"
```

Coverage reports are generated to `htmlcov/`. Minimum coverage threshold is 80%.

### Testing patterns

- HTTP mocking uses `respx` (not `responses`)
- Factory fixtures in `conftest.py`: `torrent_factory`, `metadata_factory`, `torrent_group_factory`
- HTML fixtures for nyaa.si pages: `sample_search_page_html`, `sample_detail_page_html`
- Use `mock_console` fixture to suppress Rich output

## Dependencies

| Package | Purpose |
|---|---|
| typer | CLI framework with Rich integration |
| httpx | HTTP client |
| beautifulsoup4 + lxml | HTML parsing |
| rich | Terminal output, progress bars, tables |
| pydantic | Data validation |
