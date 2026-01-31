"""Unit tests for anime_scraper.grouper."""

import pytest
from anime_scraper.grouper import (
    group_torrents_deterministic,
    group_torrents_with_metadata,
)
from anime_scraper.models import TorrentMetadata


class TestGroupTorrentsDeterministic:
    """Tests for deterministic grouping algorithm."""

    def test_same_metadata_forms_single_group(self, torrent_factory, metadata_factory):
        """Test torrents with identical metadata form one group."""
        metadata = metadata_factory(
            release_group="SubsPlease",
            anime_name="Test Anime",
            season="Season 1",
            quality="1080p",
        )

        torrents = [
            torrent_factory(id="1", name="Episode 01", metadata=metadata),
            torrent_factory(id="2", name="Episode 02", metadata=metadata),
            torrent_factory(id="3", name="Episode 03", metadata=metadata),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert len(groups) == 1
        assert len(groups[0].torrents) == 3

    def test_different_quality_creates_separate_groups(
        self, torrent_factory, metadata_factory
    ):
        """Test different quality creates separate groups."""
        metadata_1080p = metadata_factory(quality="1080p", release_group="Group")
        metadata_720p = metadata_factory(quality="720p", release_group="Group")

        torrents = [
            torrent_factory(id="1", metadata=metadata_1080p),
            torrent_factory(id="2", metadata=metadata_720p),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert len(groups) == 2

    def test_different_release_group_creates_separate_groups(
        self, torrent_factory, metadata_factory
    ):
        """Test different release groups create separate groups."""
        metadata1 = metadata_factory(release_group="SubsPlease")
        metadata2 = metadata_factory(release_group="Erai-raws")

        torrents = [
            torrent_factory(id="1", metadata=metadata1),
            torrent_factory(id="2", metadata=metadata2),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert len(groups) == 2

    def test_different_season_creates_separate_groups(
        self, torrent_factory, metadata_factory
    ):
        """Test different seasons create separate groups."""
        metadata_s1 = metadata_factory(season="Season 1", release_group="Group")
        metadata_s2 = metadata_factory(season="Season 2", release_group="Group")

        torrents = [
            torrent_factory(id="1", metadata=metadata_s1),
            torrent_factory(id="2", metadata=metadata_s2),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert len(groups) == 2

    def test_different_audio_language_creates_separate_groups(
        self, torrent_factory, metadata_factory
    ):
        """Test different audio languages create separate groups."""
        metadata_eng = metadata_factory(
            audio_language="English", release_group="Group"
        )
        metadata_jpn = metadata_factory(
            audio_language="Japanese", release_group="Group"
        )

        torrents = [
            torrent_factory(id="1", metadata=metadata_eng),
            torrent_factory(id="2", metadata=metadata_jpn),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert len(groups) == 2

    def test_groups_sorted_by_seeders_descending(
        self, torrent_factory, metadata_factory
    ):
        """Test groups are sorted by total seeders (descending)."""
        metadata1 = metadata_factory(release_group="Group1")
        metadata2 = metadata_factory(release_group="Group2")

        torrents = [
            torrent_factory(id="1", seeders=50, metadata=metadata1),
            torrent_factory(id="2", seeders=100, metadata=metadata2),
            torrent_factory(id="3", seeders=30, metadata=metadata1),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        # Group2 has 100 seeders, Group1 has 50+30=80
        assert groups[0].total_seeders == 100
        assert groups[1].total_seeders == 80

    def test_episode_range_single_episode(self, torrent_factory, metadata_factory):
        """Test episode range for single episode."""
        metadata = metadata_factory(episode="Episode 1")
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].episode_range == "Episode 1"

    def test_episode_range_multiple_episodes(self, torrent_factory, metadata_factory):
        """Test episode range for multiple episodes."""
        base_kwargs = {
            "release_group": "Group",
            "anime_name": "Anime",
            "season": "Season 1",
            "quality": "1080p",
            "audio_language": "Japanese",
            "subtitle_language": "English",
        }

        torrents = [
            torrent_factory(
                id="1",
                metadata=TorrentMetadata(**{**base_kwargs, "episode": "Episode 1"}),
            ),
            torrent_factory(
                id="2",
                metadata=TorrentMetadata(**{**base_kwargs, "episode": "Episode 5"}),
            ),
            torrent_factory(
                id="3",
                metadata=TorrentMetadata(**{**base_kwargs, "episode": "Episode 3"}),
            ),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].episode_range == "Episodes 1-5"

    def test_episode_range_various_when_no_episodes(
        self, torrent_factory, metadata_factory
    ):
        """Test episode range is 'Various' when no episode numbers."""
        metadata = metadata_factory(episode="")
        torrents = [
            torrent_factory(id="1", metadata=metadata),
            torrent_factory(id="2", metadata=metadata),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].episode_range == "Various"

    def test_is_dubbed_for_english_audio(self, torrent_factory, metadata_factory):
        """Test is_dubbed is True for English audio."""
        metadata = metadata_factory(audio_language="English")
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].is_dubbed is True

    def test_is_dubbed_for_japanese_audio(self, torrent_factory, metadata_factory):
        """Test is_dubbed is False for Japanese audio."""
        metadata = metadata_factory(audio_language="Japanese")
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].is_dubbed is False

    def test_is_dubbed_from_torrent_name_keywords(
        self, torrent_factory, metadata_factory
    ):
        """Test is_dubbed detection from torrent name keywords."""
        metadata = metadata_factory(audio_language="Unknown")
        torrents = [
            torrent_factory(
                id="1", name="Anime [Dual Audio]", metadata=metadata
            ),
        ]

        groups = group_torrents_deterministic(torrents, "Test Anime")

        assert groups[0].is_dubbed is True

    def test_empty_list_returns_empty_groups(self):
        """Test empty list returns empty groups."""
        groups = group_torrents_deterministic([], "Test Anime")
        assert len(groups) == 0

    def test_fallback_metadata_when_none(self, torrent_factory):
        """Test creates fallback metadata when None."""
        torrents = [torrent_factory(id="1", metadata=None)]

        groups = group_torrents_deterministic(torrents, "Fallback Anime")

        assert len(groups) == 1
        assert groups[0].torrents[0].metadata is not None
        assert groups[0].torrents[0].metadata.anime_name == "Fallback Anime"

    def test_group_name_uses_metadata(self, torrent_factory, metadata_factory):
        """Test group name is derived from metadata."""
        metadata = metadata_factory(
            release_group="SubsPlease",
            anime_name="Frieren",
            season="Season 1",
        )
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Frieren")

        assert "SubsPlease" in groups[0].name
        assert "Frieren" in groups[0].name

    def test_group_description_contains_metadata(
        self, torrent_factory, metadata_factory
    ):
        """Test group description contains metadata info."""
        metadata = metadata_factory(
            release_group="TestGroup",
            quality="1080p",
            audio_language="Japanese",
            subtitle_language="English",
        )
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Anime")

        assert "TestGroup" in groups[0].description
        assert "1080p" in groups[0].description

    def test_group_quality_set_from_metadata(self, torrent_factory, metadata_factory):
        """Test group quality is set from metadata."""
        metadata = metadata_factory(quality="720p")
        torrents = [torrent_factory(metadata=metadata)]

        groups = group_torrents_deterministic(torrents, "Anime")

        assert groups[0].quality == "720p"


class TestGroupingKeyBehavior:
    """Tests for grouping key behavior and determinism."""

    def test_grouping_is_deterministic(self, torrent_factory, metadata_factory):
        """Test that grouping produces consistent results."""
        metadata = metadata_factory()

        torrents = [
            torrent_factory(id=str(i), metadata=metadata)
            for i in range(5)
        ]

        groups1 = group_torrents_deterministic(torrents, "Test")
        groups2 = group_torrents_deterministic(torrents, "Test")

        assert len(groups1) == len(groups2)
        assert groups1[0].name == groups2[0].name

    def test_all_metadata_fields_affect_grouping(
        self, torrent_factory, metadata_factory
    ):
        """Test all metadata fields affect group key."""
        fields = [
            "release_group",
            "anime_name",
            "season",
            "audio_language",
            "subtitle_language",
            "quality",
        ]

        for field in fields:
            metadata1 = metadata_factory(**{field: "Value1"})
            metadata2 = metadata_factory(**{field: "Value2"})

            torrents = [
                torrent_factory(id="1", metadata=metadata1),
                torrent_factory(id="2", metadata=metadata2),
            ]

            groups = group_torrents_deterministic(torrents, "Test")
            assert (
                len(groups) == 2
            ), f"Field '{field}' did not affect grouping"
