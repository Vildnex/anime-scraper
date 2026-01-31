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

## Full Example

### 1. Run the command

```bash
anime-scraper search "The Daily Life of the Immortal King"
```

### 2. The tool searches nyaa.si and fetches submitter info

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ANIME SCRAPER                                            ║
║     Search, Group & Download Anime from Nyaa.si              ║
║     Deterministic Grouping                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Searching for: The Daily Life of the Immortal King

Step 1: Searching nyaa.si...
⠴ Fetching submitter 375/375...
Found 375 torrents
```

### 3. Select language preferences

```
Step 2: Language Preferences

Language Preferences
Filter torrents by audio and subtitle language

Audio Language Options:
  0. Any
  1. English
  2. Japanese
  3. Spanish
  4. Portuguese
  5. French
  6. German
  7. Italian
  8. Chinese

Select audio language (number or name) (0): 0

Subtitle Language Options:
  0. Any
  1. English
  2. Spanish
  3. Portuguese
  4. French
  5. German
  6. Italian
  7. Chinese
  8. Arabic
  9. Multi

Select subtitle language (number or name) (0): 1

Selected: Audio=Any, Subtitles=English
Filtered: 120/375 torrents match your language preferences
```

### 4. Metadata is extracted and torrents are grouped

```
Step 3: Extracting metadata and grouping...

Fetching torrent details for metadata extraction...
  Fetching details for: [Yameii] The Daily Life of the Immortal ... ━━━━━━━━━━━━━━━━━━━━ 100%
Extracted metadata for 120 torrents

Grouping torrents by metadata...
Created 28 groups (deterministic)
```

### 5. Browse groups and select one to download

```
Step 4: Select a group to download
                                    Torrent Groups
╭──────┬──────────────────────────────────┬────────┬──────────┬─────────┬────────┬──────────┬─────────╮
│ #    │ Group Name                       │ Season │ Episodes │ Quality │ Dubbed │ Torrents │ Total   │
│      │                                  │        │          │         │        │          │ Seeders │
├──────┼──────────────────────────────────┼────────┼──────────┼─────────┼────────┼──────────┼─────────┤
│ 1    │ Yameii - The Daily Life of th... │ S4     │ Ep 1-12  │ 1080p   │ Yes    │ 21       │ 188     │
│ 2    │ sff - The Daily Life Of The I... │ S1     │ Various  │ 1080p   │ Yes    │ 1        │ 157     │
│ 3    │ Yameii - Xian Wang De Richang... │ S2     │ Ep 1-15  │ 1080p   │ Yes    │ 15       │ 67      │
│ 4    │ Yameii - The Daily Life of th... │ S5     │ Ep 1     │ 1080p   │ Yes    │ 1        │ 55      │
│ 5    │ Yameii - The Daily Life of th... │ S4     │ Ep 1-12  │ 720p    │ Yes    │ 15       │ 49      │
│ ...  │ ...                              │ ...    │ ...      │ ...     │ ...    │ ...      │ ...     │
│ 28   │ Metaljerk - The Daily Life of... │ S1     │ Ep 13    │ 1080p   │ Yes    │ 1        │ 0       │
╰──────┴──────────────────────────────────┴────────┴──────────┴─────────┴────────┴──────────┴─────────╯

Options:
  1-{n} - View group details and download options
  q     - Quit without downloading

Select a group number to view details (q):
```

Select a group number to review individual torrents, confirm the download, and the tool saves `.torrent` files and/or a magnet bundle to your output directory.

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
