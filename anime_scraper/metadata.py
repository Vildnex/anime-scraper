"""Metadata extraction from nyaa.si detail pages."""

import re
import httpx
from bs4 import BeautifulSoup

from .cache import CachedHTTPClient
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .models import Torrent, TorrentMetadata
from .utils import console

BASE_URL = "https://nyaa.si"

# Regex patterns for extracting metadata from titles
PATTERNS = {
    # Release group: [GroupName] or (GroupName) at the start
    "release_group_start": re.compile(r"^\[([^\]]+)\]|^\(([^)]+)\)"),
    # Scene release group at end: -GROUPNAME or -GROUP at the very end
    "release_group_end": re.compile(r"-([A-Za-z0-9]+)(?:\.[a-z]{2,4})?$"),
    # Season: S01, Season 1, S1, Season 01, etc.
    "season": re.compile(r"(?:S|Season\s?)(\d+)", re.IGNORECASE),
    # Season (Part): Part 1, Part 2 (split-cour anime)
    "season_part": re.compile(r"Part\s+(\d+)", re.IGNORECASE),
    # Season (Cour): Cour 1, Cour 2 (Japanese broadcast terms)
    "season_cour": re.compile(r"Cour\s+(\d+)", re.IGNORECASE),
    # Season (Ordinal numeric): 2nd Season, 3rd Season
    "season_ordinal_num": re.compile(r"(\d+)(?:st|nd|rd|th)\s+Season", re.IGNORECASE),
    # Season (Ordinal word): Second Season, Third Season
    "season_ordinal_word": re.compile(
        r"(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\s+Season",
        re.IGNORECASE,
    ),
    # Season (Roman numeral): Season II, Season III
    "season_roman": re.compile(r"Season\s+([IVX]+)\b", re.IGNORECASE),
    # Episode: E01, Ep 01, Episode 01, - 01, etc.
    "episode": re.compile(
        r"(?:E|Ep\.?\s?|Episode\s?)(\d+)|[\s\-]\s?(\d{2,3})(?:\s|$|\[|\()",
        re.IGNORECASE,
    ),
    # Quality: 1080p, 720p, 480p, 4K, 2160p, FHD, HD
    "quality": re.compile(
        r"(4K|2160p|1080p|720p|480p|360p|FHD|HD|1920x1080|1280x720|SD)",
        re.IGNORECASE,
    ),
    # Audio language indicators - includes "DUAL" alone
    "audio_english": re.compile(
        r"(English\s*Dub|Eng\s*Dub|Dubbed|Dual\s*Audio|\bDUAL\b|\bDub\b)",
        re.IGNORECASE,
    ),
    "audio_japanese": re.compile(r"(Japanese|JPN|Raw|\bJap\b)", re.IGNORECASE),
    # Subtitle language indicators
    "sub_english": re.compile(
        r"(English\s*Sub|Eng\s*Sub|Subbed|\bSub\b|\[Eng\]|English)",
        re.IGNORECASE,
    ),
    "sub_multi": re.compile(r"(Multi-?Sub|MultiSub)", re.IGNORECASE),
}


def extract_release_group(title: str) -> str:
    """Extract the release group from the title."""
    # Try start of title first: [GroupName] or (GroupName)
    match = PATTERNS["release_group_start"].search(title)
    if match:
        return match.group(1) or match.group(2)

    # Try end of title for scene groups: -GROUPNAME
    match = PATTERNS["release_group_end"].search(title)
    if match:
        return match.group(1)

    return "Unknown"


# Mapping for ordinal words to numbers
ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def _parse_ordinal_word(word: str) -> int:
    """Convert ordinal word to integer (e.g., 'Second' -> 2)."""
    return ORDINAL_WORDS.get(word.lower(), 1)


def _parse_roman_numeral(numeral: str) -> int:
    """Convert Roman numeral to integer (e.g., 'III' -> 3)."""
    roman_values = {"I": 1, "V": 5, "X": 10}
    result = 0
    prev_value = 0
    for char in reversed(numeral.upper()):
        value = roman_values.get(char, 0)
        if value < prev_value:
            result -= value
        else:
            result += value
        prev_value = value
    return result if result > 0 else 1


def _extract_season_number(text: str) -> int | None:
    """
    Extract season number from text using multiple pattern strategies.

    Returns the season number if found, None otherwise.
    Priority order:
    1. Standard: S01, Season 1
    2. Ordinal numeric: 2nd Season
    3. Ordinal word: Second Season
    4. Roman numeral: Season II
    5. Part: Part 1
    6. Cour: Cour 1
    """
    # 1. Standard: S01, Season 1 (most common)
    match = PATTERNS["season"].search(text)
    if match:
        return int(match.group(1))

    # 2. Ordinal numeric: 2nd Season, 3rd Season
    match = PATTERNS["season_ordinal_num"].search(text)
    if match:
        return int(match.group(1))

    # 3. Ordinal word: Second Season, Third Season
    match = PATTERNS["season_ordinal_word"].search(text)
    if match:
        return _parse_ordinal_word(match.group(1))

    # 4. Roman numeral: Season II, Season III
    match = PATTERNS["season_roman"].search(text)
    if match:
        return _parse_roman_numeral(match.group(1))

    # 5. Part: Part 1, Part 2 (split-cour anime)
    match = PATTERNS["season_part"].search(text)
    if match:
        return int(match.group(1))

    # 6. Cour: Cour 1, Cour 2
    match = PATTERNS["season_cour"].search(text)
    if match:
        return int(match.group(1))

    return None


def extract_season(title: str, description: str = "") -> str:
    """Extract the season number from title or description."""
    # Check title first
    season_num = _extract_season_number(title)
    if season_num is not None:
        return f"Season {season_num}"

    # Check description
    season_num = _extract_season_number(description)
    if season_num is not None:
        return f"Season {season_num}"

    # Default
    return "Season 1"


def extract_episode(title: str) -> str:
    """Extract episode number(s) from title."""
    match = PATTERNS["episode"].search(title)
    if match:
        ep = match.group(1) or match.group(2)
        return f"Episode {int(ep)}"
    return ""


def extract_quality(title: str, description: str = "") -> str:
    """Extract video quality from title or description."""
    # Check title first
    match = PATTERNS["quality"].search(title)
    if match:
        return match.group(1)

    # Check description
    match = PATTERNS["quality"].search(description)
    if match:
        return match.group(1)

    return "Unknown"


def extract_audio_language(title: str, description: str, category: str) -> str:
    """Extract audio language from title, description, or category."""
    combined = f"{title} {description}"

    # Check for English dub indicators
    if PATTERNS["audio_english"].search(combined):
        return "English"

    # Check for Japanese/Raw indicators
    if PATTERNS["audio_japanese"].search(combined):
        return "Japanese"

    # Use category as fallback
    if "Raw" in category:
        return "Japanese"

    return "Japanese"  # Default for anime


def extract_subtitle_language(title: str, description: str, category: str) -> str:
    """Extract subtitle language from title, description, or category."""
    combined = f"{title} {description}"

    # Check for multi-sub
    if PATTERNS["sub_multi"].search(combined):
        return "Multi"

    # Check for English sub indicators
    if PATTERNS["sub_english"].search(combined):
        return "English"

    # Use category as fallback
    if "English-translated" in category:
        return "English"
    elif "Raw" in category:
        return "None"

    return "Unknown"


def extract_anime_name(title: str) -> str:
    """Extract the anime name from the title."""
    # Remove release group at start
    name = PATTERNS["release_group_start"].sub("", title).strip()

    # Remove common suffixes/patterns
    # Remove standard season indicator (S01, Season 1)
    name = re.sub(r"\s*(?:S|Season\s?)\d+.*", "", name, flags=re.IGNORECASE)
    # Remove ordinal season (2nd Season, Second Season)
    name = re.sub(r"\s*\d+(?:st|nd|rd|th)\s+Season.*", "", name, flags=re.IGNORECASE)
    name = re.sub(
        r"\s*(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\s+Season.*",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove Roman numeral season (Season II)
    name = re.sub(r"\s*Season\s+[IVX]+\b.*", "", name, flags=re.IGNORECASE)
    # Remove Part indicator (Part 1)
    name = re.sub(r"\s*Part\s+\d+.*", "", name, flags=re.IGNORECASE)
    # Remove Cour indicator (Cour 1)
    name = re.sub(r"\s*Cour\s+\d+.*", "", name, flags=re.IGNORECASE)
    # Remove episode indicator
    name = re.sub(r"\s*(?:E|Ep\.?\s?|Episode\s?)\d+.*", "", name, flags=re.IGNORECASE)
    # Remove trailing episode number like " - 01"
    name = re.sub(r"\s*-\s*\d+.*", "", name)
    # Remove quality and other metadata in brackets/parentheses at the end
    name = re.sub(r"\s*[\[\(][^\]\)]*[\]\)]\s*$", "", name)
    # Remove trailing brackets/metadata
    name = re.sub(r"\s*[\[\(].*$", "", name)

    return name.strip() or "Unknown"


def fetch_detail_page(client: httpx.Client | CachedHTTPClient, torrent_id: str) -> dict | None:
    """Fetch and parse a torrent's detail page."""
    try:
        response = client.get(f"{BASE_URL}/view/{torrent_id}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        result = {
            "title": "",
            "submitter": "Anonymous",
            "category": "",
            "description": "",
            "file_list": [],
        }

        # Extract title
        title_elem = soup.select_one("h3.panel-title")
        if title_elem:
            result["title"] = title_elem.get_text(strip=True)

        # Extract submitter
        rows = soup.select(".panel-body .row")
        for row in rows:
            label = row.find(class_="col-md-1")
            if label:
                label_text = label.get_text(strip=True)
                value = row.find(class_="col-md-5")
                if value:
                    if "Submitter:" in label_text:
                        result["submitter"] = value.get_text(strip=True)
                    elif "Category:" in label_text:
                        result["category"] = value.get_text(strip=True)

        # Extract description
        desc_elem = soup.select_one("#torrent-description")
        if desc_elem:
            result["description"] = desc_elem.get_text(strip=True)

        # Extract file list
        file_list = soup.select(".torrent-file-list li")
        for file_elem in file_list:
            filename = file_elem.get_text(strip=True)
            # Remove size info if present
            filename = re.sub(r"\s*\(\d+.*?\)\s*$", "", filename)
            if filename:
                result["file_list"].append(filename)

        return result

    except Exception as e:
        console.print(f"[yellow]Warning: Failed to fetch detail page for {torrent_id}: {e}[/yellow]")
        return None


def extract_metadata_from_detail(detail: dict) -> TorrentMetadata:
    """Extract all metadata from a detail page result."""
    title = detail.get("title", "")
    description = detail.get("description", "")
    category = detail.get("category", "")
    submitter = detail.get("submitter", "Anonymous")

    # Use the actual submitter from nyaa.si as the "release_group" for grouping
    # This ensures consistent grouping by uploader account
    release_group = submitter if submitter and submitter != "Anonymous" else extract_release_group(title)

    return TorrentMetadata(
        anime_name=extract_anime_name(title),
        season=extract_season(title, description),
        episode=extract_episode(title),
        quality=extract_quality(title, description),
        audio_language=extract_audio_language(title, description, category),
        subtitle_language=extract_subtitle_language(title, description, category),
        release_group=release_group,
        description=description[:200] if description else "",
    )


def fetch_metadata_for_torrents(torrents: list[Torrent]) -> list[Torrent]:
    """
    Fetch detail pages and extract metadata for all torrents.

    Args:
        torrents: List of Torrent objects

    Returns:
        The same list with metadata populated
    """
    if not torrents:
        return torrents

    with CachedHTTPClient(current_query=None, timeout=30.0, follow_redirects=True) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Fetching torrent details...", total=len(torrents)
            )

            for torrent in torrents:
                progress.update(
                    task,
                    description=f"Fetching details for: {torrent.name[:40]}...",
                )

                detail = fetch_detail_page(client, torrent.id)
                if detail:
                    torrent.metadata = extract_metadata_from_detail(detail)
                    torrent.submitter = detail.get("submitter", "Anonymous")
                else:
                    # Fallback: extract from the name we already have
                    torrent.metadata = TorrentMetadata(
                        anime_name=extract_anime_name(torrent.name),
                        season=extract_season(torrent.name, ""),
                        episode=extract_episode(torrent.name),
                        quality=extract_quality(torrent.name, ""),
                        audio_language="Unknown",
                        subtitle_language="Unknown",
                        release_group=extract_release_group(torrent.name),
                    )

                progress.advance(task)

    console.print(f"[green]Extracted metadata for {len(torrents)} torrents[/green]")
    return torrents
