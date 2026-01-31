"""Shared pytest fixtures for anime-scraper tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from anime_scraper.models import Torrent, TorrentMetadata, TorrentGroup


# ============================================================================
# Factory Fixtures - Create test data on demand
# ============================================================================


@pytest.fixture
def metadata_factory():
    """Factory for creating test TorrentMetadata objects."""

    def _create(
        anime_name: str = "Test Anime",
        season: str = "Season 1",
        episode: str = "Episode 1",
        quality: str = "1080p",
        audio_language: str = "Japanese",
        subtitle_language: str = "English",
        release_group: str = "SubsPlease",
        description: str = "Test description",
    ) -> TorrentMetadata:
        return TorrentMetadata(
            anime_name=anime_name,
            season=season,
            episode=episode,
            quality=quality,
            audio_language=audio_language,
            subtitle_language=subtitle_language,
            release_group=release_group,
            description=description,
        )

    return _create


@pytest.fixture
def torrent_factory(metadata_factory):
    """Factory for creating test Torrent objects with customizable fields."""

    def _create(
        id: str = "12345",
        name: str = "[SubsPlease] Test Anime - 01 (1080p) [ABC123].mkv",
        magnet: str = "magnet:?xt=urn:btih:ABC123",
        torrent_url: str = "https://nyaa.si/download/12345.torrent",
        size: str = "1.4 GiB",
        date: str = "2024-01-15 12:00",
        seeders: int = 100,
        leechers: int = 10,
        downloads: int = 500,
        category: str = "Anime - English-translated",
        submitter: str = "SubsPlease",
        metadata: TorrentMetadata | None = None,
    ) -> Torrent:
        return Torrent(
            id=id,
            name=name,
            magnet=magnet,
            torrent_url=torrent_url,
            size=size,
            date=date,
            seeders=seeders,
            leechers=leechers,
            downloads=downloads,
            category=category,
            submitter=submitter,
            metadata=metadata,
        )

    return _create


@pytest.fixture
def torrent_group_factory(torrent_factory, metadata_factory):
    """Factory for creating test TorrentGroup objects."""

    def _create(
        name: str = "SubsPlease - Test Anime - Season 1 - SUB English - QUALITY 1080p",
        description: str = "Release group: SubsPlease, Quality: 1080p",
        num_torrents: int = 3,
        episode_range: str = "Episodes 1-3",
        quality: str = "1080p",
        is_dubbed: bool = False,
    ) -> TorrentGroup:
        metadata = metadata_factory()
        torrents = [
            torrent_factory(
                id=str(i),
                name=f"[SubsPlease] Test Anime - {i:02d} (1080p) [ABC{i}].mkv",
                seeders=100 - i * 10,
                metadata=metadata,
            )
            for i in range(1, num_torrents + 1)
        ]

        return TorrentGroup(
            name=name,
            description=description,
            torrents=torrents,
            episode_range=episode_range,
            quality=quality,
            is_dubbed=is_dubbed,
        )

    return _create


# ============================================================================
# HTML Mock Data - Realistic nyaa.si HTML fixtures
# ============================================================================


@pytest.fixture
def sample_search_page_html():
    """Sample nyaa.si search results page HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <table class="torrent-list">
            <tbody>
                <tr>
                    <td><a href="/?c=1_2" title="Anime - English-translated">Anime</a></td>
                    <td>
                        <a href="/view/1234567" title="[SubsPlease] Test Anime - 01 (1080p) [ABCDEF].mkv">
                            [SubsPlease] Test Anime - 01 (1080p) [ABCDEF].mkv
                        </a>
                    </td>
                    <td>
                        <a href="magnet:?xt=urn:btih:ABCDEF">Magnet</a>
                        <a href="/download/1234567.torrent">Torrent</a>
                    </td>
                    <td>1.4 GiB</td>
                    <td>2024-01-15 12:00</td>
                    <td>150</td>
                    <td>20</td>
                    <td>1000</td>
                </tr>
                <tr>
                    <td><a href="/?c=1_2" title="Anime - English-translated">Anime</a></td>
                    <td>
                        <a href="/view/1234568" title="[SubsPlease] Test Anime - 02 (1080p) [GHIJKL].mkv">
                            [SubsPlease] Test Anime - 02 (1080p) [GHIJKL].mkv
                        </a>
                    </td>
                    <td>
                        <a href="magnet:?xt=urn:btih:GHIJKL">Magnet</a>
                        <a href="/download/1234568.torrent">Torrent</a>
                    </td>
                    <td>1.5 GiB</td>
                    <td>2024-01-16 12:00</td>
                    <td>120</td>
                    <td>15</td>
                    <td>800</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_page_html():
    """Sample nyaa.si torrent detail page HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <div class="panel">
            <h3 class="panel-title">[SubsPlease] Test Anime - 01 (1080p) [ABCDEF].mkv</h3>
            <div class="panel-body">
                <div class="row">
                    <div class="col-md-1">Submitter:</div>
                    <div class="col-md-5">SubsPlease</div>
                </div>
                <div class="row">
                    <div class="col-md-1">Category:</div>
                    <div class="col-md-5">Anime - English-translated</div>
                </div>
            </div>
        </div>
        <div id="torrent-description">
            Test Anime Season 1 Episode 1
            Video: 1920x1080 (1080p)
            Audio: Japanese
            Subtitles: English
        </div>
        <ul class="torrent-file-list">
            <li>[SubsPlease] Test Anime - 01 (1080p) [ABCDEF].mkv (1.4 GiB)</li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def empty_search_page_html():
    """Empty search results page (no torrents found)."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <p>No results found.</p>
    </body>
    </html>
    """


# ============================================================================
# Filesystem Fixtures
# ============================================================================


@pytest.fixture
def temp_download_dir(tmp_path):
    """Temporary download directory for testing file operations."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


@pytest.fixture
def sample_torrent_file_content():
    """Mock .torrent file binary content."""
    return b"d8:announce41:http://tracker.example.com:1337/announce13:creation datei1234567890e4:infod6:lengthi1468006000e4:name39:[SubsPlease] Test Anime - 01 (1080p).mkvee"


# ============================================================================
# Console Mocking
# ============================================================================


@pytest.fixture
def mock_console(monkeypatch):
    """Mock Rich console to suppress output in tests."""
    from anime_scraper import utils

    mock = MagicMock()
    monkeypatch.setattr(utils, "console", mock)
    return mock


# ============================================================================
# Cache Fixtures
# ============================================================================


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Temporary cache directory for isolated testing."""
    cache_dir = tmp_path / "anime_cache"
    cache_dir.mkdir()
    # Patch cache module constants to use temp dir
    import anime_scraper.cache as cache_module
    monkeypatch.setattr(cache_module, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cache_module, "METADATA_FILE", cache_dir / "metadata.json")
    monkeypatch.setattr(cache_module, "CACHE_SUBDIR", cache_dir / "html_cache")
    return cache_dir
