"""Unit tests for anime_scraper.models."""

import pytest
from anime_scraper.models import Torrent, TorrentMetadata, TorrentGroup


class TestTorrentMetadata:
    """Tests for TorrentMetadata model."""

    def test_group_key_deterministic(self, metadata_factory):
        """Test that group_key produces consistent results."""
        metadata = metadata_factory(
            release_group="SubsPlease",
            anime_name="Test Anime",
            season="Season 1",
            audio_language="Japanese",
            subtitle_language="English",
            quality="1080p",
        )

        expected_key = "SubsPlease|Test Anime|Season 1|Japanese|English|1080p"
        assert metadata.group_key() == expected_key

    def test_group_key_different_metadata_different_keys(self, metadata_factory):
        """Different metadata should produce different keys."""
        meta1 = metadata_factory(quality="1080p")
        meta2 = metadata_factory(quality="720p")

        assert meta1.group_key() != meta2.group_key()

    @pytest.mark.parametrize(
        "field,value1,value2",
        [
            ("release_group", "GroupA", "GroupB"),
            ("anime_name", "Anime1", "Anime2"),
            ("season", "Season 1", "Season 2"),
            ("audio_language", "English", "Japanese"),
            ("subtitle_language", "English", "Spanish"),
            ("quality", "1080p", "720p"),
        ],
    )
    def test_group_key_varies_by_field(self, metadata_factory, field, value1, value2):
        """Test that group_key varies for each metadata field."""
        meta1 = metadata_factory(**{field: value1})
        meta2 = metadata_factory(**{field: value2})

        assert meta1.group_key() != meta2.group_key()

    def test_group_name_format(self, metadata_factory):
        """Test group_name formatting with all metadata."""
        metadata = metadata_factory(
            release_group="SubsPlease",
            anime_name="Test Anime",
            season="Season 1",
            audio_language="English",
            subtitle_language="Spanish",
            quality="1080p",
        )

        name = metadata.group_name()
        assert "SubsPlease" in name
        assert "Test Anime" in name
        assert "Season 1" in name
        assert "DUB English" in name
        assert "SUB Spanish" in name
        assert "QUALITY 1080p" in name

    def test_group_name_excludes_unknown_audio(self, metadata_factory):
        """Test group_name excludes Unknown audio language."""
        metadata = metadata_factory(
            release_group="Group",
            anime_name="Test",
            season="Season 1",
            audio_language="Unknown",
            subtitle_language="English",
            quality="1080p",
        )

        name = metadata.group_name()
        assert "DUB" not in name
        assert "SUB English" in name

    def test_group_name_excludes_unknown_subtitle(self, metadata_factory):
        """Test group_name excludes Unknown subtitle language."""
        metadata = metadata_factory(
            release_group="Group",
            anime_name="Test",
            season="Season 1",
            audio_language="Japanese",
            subtitle_language="Unknown",
            quality="1080p",
        )

        name = metadata.group_name()
        assert "SUB" not in name

    def test_group_name_excludes_unknown_quality(self, metadata_factory):
        """Test group_name excludes Unknown quality."""
        metadata = metadata_factory(
            release_group="Group",
            anime_name="Test",
            season="Season 1",
            audio_language="Japanese",
            subtitle_language="English",
            quality="Unknown",
        )

        name = metadata.group_name()
        assert "QUALITY" not in name

    def test_default_values(self):
        """Test TorrentMetadata default values."""
        metadata = TorrentMetadata()

        assert metadata.anime_name == "Unknown"
        assert metadata.season == "Season 1"
        assert metadata.episode == ""
        assert metadata.quality == "Unknown"
        assert metadata.audio_language == "Unknown"
        assert metadata.subtitle_language == "Unknown"
        assert metadata.release_group == "Unknown"
        assert metadata.description == ""

    @pytest.mark.parametrize(
        "season,expected",
        [
            ("Season 1", "S1"),
            ("Season 2", "S2"),
            ("Season 10", "S10"),
            ("Season 99", "S99"),
            ("season 3", "S3"),  # Case insensitive
        ],
    )
    def test_season_short_format(self, season, expected):
        """Test season_short returns correct short format."""
        metadata = TorrentMetadata(season=season)
        assert metadata.season_short() == expected

    def test_season_short_default(self):
        """Test season_short returns S1 for unrecognized format."""
        metadata = TorrentMetadata(season="Unknown")
        assert metadata.season_short() == "S1"

    def test_season_short_with_factory(self, metadata_factory):
        """Test season_short with factory-created metadata."""
        metadata = metadata_factory(season="Season 5")
        assert metadata.season_short() == "S5"


class TestTorrent:
    """Tests for Torrent model."""

    def test_download_url_property(self, torrent_factory):
        """Test download_url generates correct URL."""
        torrent = torrent_factory(id="123456")
        assert torrent.download_url == "https://nyaa.si/download/123456.torrent"

    def test_download_url_different_ids(self, torrent_factory):
        """Test download_url with different IDs."""
        t1 = torrent_factory(id="111")
        t2 = torrent_factory(id="999")

        assert t1.download_url == "https://nyaa.si/download/111.torrent"
        assert t2.download_url == "https://nyaa.si/download/999.torrent"

    def test_str_representation(self, torrent_factory):
        """Test string representation includes key info."""
        torrent = torrent_factory(
            name="Test Torrent",
            size="1.5 GiB",
            seeders=100,
            leechers=20,
        )

        result = str(torrent)
        assert "Test Torrent" in result
        assert "1.5 GiB" in result
        assert "S:100" in result
        assert "L:20" in result

    def test_default_submitter(self, torrent_factory):
        """Test default submitter value."""
        # Create torrent without specifying submitter
        torrent = Torrent(
            id="1",
            name="Test",
            magnet="magnet:",
            torrent_url="https://example.com",
            size="1GB",
            date="2024-01-01",
            seeders=10,
            leechers=5,
            downloads=100,
            category="Anime",
        )
        assert torrent.submitter == "Anonymous"

    def test_metadata_can_be_none(self, torrent_factory):
        """Test that metadata can be None."""
        torrent = torrent_factory(metadata=None)
        assert torrent.metadata is None

    def test_metadata_can_be_set(self, torrent_factory, metadata_factory):
        """Test that metadata can be set."""
        metadata = metadata_factory(anime_name="Frieren")
        torrent = torrent_factory(metadata=metadata)

        assert torrent.metadata is not None
        assert torrent.metadata.anime_name == "Frieren"


class TestTorrentGroup:
    """Tests for TorrentGroup model."""

    def test_total_size_property(self, torrent_group_factory):
        """Test total_size returns torrent count."""
        group = torrent_group_factory(num_torrents=5)
        assert group.total_size == "5 torrents"

    def test_total_size_single_torrent(self, torrent_group_factory):
        """Test total_size with single torrent."""
        group = torrent_group_factory(num_torrents=1)
        assert group.total_size == "1 torrents"

    def test_total_seeders_calculation(self, torrent_group_factory):
        """Test total_seeders sums all torrent seeders."""
        group = torrent_group_factory(num_torrents=3)
        # Factory creates torrents with seeders: 90, 80, 70
        expected_total = 90 + 80 + 70
        assert group.total_seeders == expected_total

    def test_total_seeders_empty_group(self, torrent_factory):
        """Test total_seeders with no torrents."""
        group = TorrentGroup(
            name="Empty Group",
            description="No torrents",
            torrents=[],
        )
        assert group.total_seeders == 0

    def test_str_representation(self, torrent_group_factory):
        """Test string representation."""
        group = torrent_group_factory(
            name="Test Group",
            num_torrents=10,
        )

        result = str(group)
        assert "Test Group" in result
        assert "10 torrents" in result

    def test_default_values(self, torrent_factory):
        """Test TorrentGroup default values."""
        group = TorrentGroup(
            name="Test",
            description="Desc",
        )

        assert group.torrents == []
        assert group.episode_range == ""
        assert group.quality == ""
        assert group.is_dubbed is False

    def test_is_dubbed_flag(self, torrent_group_factory):
        """Test is_dubbed flag."""
        group_dubbed = torrent_group_factory(is_dubbed=True)
        group_not_dubbed = torrent_group_factory(is_dubbed=False)

        assert group_dubbed.is_dubbed is True
        assert group_not_dubbed.is_dubbed is False
