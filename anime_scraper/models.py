"""Data models for anime scraper."""

import re
from dataclasses import dataclass, field


@dataclass
class TorrentMetadata:
    """Extracted metadata from a torrent's detail page."""

    anime_name: str = "Unknown"
    season: str = "Season 1"
    episode: str = ""
    quality: str = "Unknown"
    audio_language: str = "Unknown"
    subtitle_language: str = "Unknown"
    release_group: str = "Unknown"
    description: str = ""

    def group_key(self) -> str:
        """Generate a deterministic grouping key."""
        return f"{self.release_group}|{self.anime_name}|{self.season}|{self.audio_language}|{self.subtitle_language}|{self.quality}"

    def season_short(self) -> str:
        """Return short season format (e.g., 'S1', 'S2')."""
        match = re.search(r"Season\s*(\d+)", self.season, re.IGNORECASE)
        if match:
            return f"S{match.group(1)}"
        return "S1"

    def group_name(self) -> str:
        """Generate the formatted group name."""
        parts = [self.release_group, self.anime_name, self.season]
        if self.audio_language and self.audio_language != "Unknown":
            parts.append(f"DUB {self.audio_language}")
        if self.subtitle_language and self.subtitle_language != "Unknown":
            parts.append(f"SUB {self.subtitle_language}")
        if self.quality and self.quality != "Unknown":
            parts.append(f"QUALITY {self.quality}")
        return " - ".join(parts)


@dataclass
class Torrent:
    """Represents a single torrent from nyaa.si."""

    id: str
    name: str
    magnet: str
    torrent_url: str
    size: str
    date: str
    seeders: int
    leechers: int
    downloads: int
    category: str
    submitter: str = "Anonymous"
    metadata: TorrentMetadata | None = None

    @property
    def download_url(self) -> str:
        """Direct .torrent file download URL."""
        return f"https://nyaa.si/download/{self.id}.torrent"

    def __str__(self) -> str:
        return f"{self.name} [{self.size}] S:{self.seeders} L:{self.leechers}"


@dataclass
class TorrentGroup:
    """A group of related torrents (e.g., same season, release group)."""

    name: str
    description: str
    torrents: list[Torrent] = field(default_factory=list)
    episode_range: str = ""
    quality: str = ""
    is_dubbed: bool = False

    @property
    def total_size(self) -> str:
        """Calculate approximate total size (simplified)."""
        return f"{len(self.torrents)} torrents"

    @property
    def total_seeders(self) -> int:
        """Sum of all seeders in the group."""
        return sum(t.seeders for t in self.torrents)

    def __str__(self) -> str:
        return f"{self.name} ({len(self.torrents)} torrents)"
