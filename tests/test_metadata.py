"""Unit tests for anime_scraper.metadata with extensive regex testing."""

import pytest
import respx
import httpx

from anime_scraper.metadata import (
    extract_release_group,
    extract_season,
    extract_episode,
    extract_quality,
    extract_audio_language,
    extract_subtitle_language,
    extract_anime_name,
    extract_metadata_from_detail,
    fetch_detail_page,
    PATTERNS,
    _parse_ordinal_word,
    _parse_roman_numeral,
    _extract_season_number,
)


class TestExtractReleaseGroup:
    """Tests for release group extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("[SubsPlease] Anime - 01", "SubsPlease"),
            ("(Erai-raws) Anime - 01", "Erai-raws"),
            ("[HorribleSubs] Anime [720p]", "HorribleSubs"),
            ("[Some-Group] Title Here", "Some-Group"),
            ("(AnotherGroup) Title", "AnotherGroup"),
        ],
    )
    def test_extract_release_group_bracket_formats(self, title, expected):
        """Test release group extraction from bracket formats."""
        assert extract_release_group(title) == expected

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime.S01E01.1080p-GROUPNAME", "GROUPNAME"),
            ("Anime.S01E01-RELEASE.mkv", "RELEASE"),
            ("Title.2024-GROUP", "GROUP"),
        ],
    )
    def test_extract_release_group_scene_format(self, title, expected):
        """Test release group extraction from scene-style naming."""
        assert extract_release_group(title) == expected

    def test_extract_release_group_no_match(self):
        """Test returns 'Unknown' when no group found."""
        assert extract_release_group("Just an anime title") == "Unknown"
        assert extract_release_group("Anime Episode 01") == "Unknown"

    def test_extract_release_group_prefers_start(self):
        """Test that [GroupName] at start takes precedence."""
        title = "[StartGroup] Anime - 01 -ENDGROUP"
        assert extract_release_group(title) == "StartGroup"


class TestExtractSeason:
    """Tests for season number extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime S01E01", "Season 1"),
            ("Anime S2 - 01", "Season 2"),
            ("Anime Season 3 Episode 01", "Season 3"),
            ("Anime Season 10", "Season 10"),
            ("[Group] Anime S04 [1080p]", "Season 4"),
            ("Anime S3E01", "Season 3"),
        ],
    )
    def test_extract_season_from_title(self, title, expected):
        """Test season extraction from titles."""
        assert extract_season(title) == expected

    def test_extract_season_from_description(self):
        """Test season extraction from description when not in title."""
        title = "Anime - 01"
        description = "This is Season 3 of the anime"
        assert extract_season(title, description) == "Season 3"

    def test_extract_season_default(self):
        """Test default season when none found."""
        title = "Anime - 01"
        assert extract_season(title) == "Season 1"

    def test_extract_season_title_precedence(self):
        """Test title takes precedence over description."""
        title = "Anime S02E01"
        description = "Season 5 content"
        assert extract_season(title, description) == "Season 2"

    def test_extract_season_normalizes_number(self):
        """Test that season numbers are normalized."""
        assert extract_season("Anime S01") == "Season 1"
        assert extract_season("Anime Season 03") == "Season 3"


class TestExtractEpisode:
    """Tests for episode number extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("[Group] Anime - 01 [1080p]", "Episode 1"),
            ("Anime E05 (720p)", "Episode 5"),
            ("Anime Episode 10", "Episode 10"),
            ("Anime - Ep 08 - Title", "Episode 8"),
            ("Anime.S01E12.1080p", "Episode 12"),
            ("Anime Ep. 03 Title", "Episode 3"),
        ],
    )
    def test_extract_episode_various_formats(self, title, expected):
        """Test episode extraction from different formats."""
        assert extract_episode(title) == expected

    def test_extract_episode_three_digit(self):
        """Test handling of three-digit episode numbers."""
        assert extract_episode("[Group] Anime - 123 [1080p]") == "Episode 123"

    def test_extract_episode_not_found(self):
        """Test returns empty string when no episode found."""
        assert extract_episode("[Group] Anime Season 1 [1080p]") == ""
        assert extract_episode("Anime Complete Series") == ""


class TestExtractQuality:
    """Tests for video quality extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime 1080p", "1080p"),
            ("Anime (720p)", "720p"),
            ("Anime [480p]", "480p"),
            ("Anime 4K", "4K"),
            ("Anime 2160p", "2160p"),
            ("Anime FHD", "FHD"),
            ("Anime HD", "HD"),
            ("Anime 1920x1080", "1920x1080"),
            ("Anime 1280x720", "1280x720"),
            ("Anime 360p", "360p"),
        ],
    )
    def test_extract_quality_various_formats(self, title, expected):
        """Test quality extraction for different resolutions."""
        result = extract_quality(title)
        assert result.lower() == expected.lower()

    def test_extract_quality_from_description(self):
        """Test quality extraction from description."""
        title = "Anime - 01"
        description = "Video quality: 1080p"
        assert extract_quality(title, description) == "1080p"

    def test_extract_quality_title_precedence(self):
        """Test title takes precedence over description."""
        title = "Anime 720p"
        description = "Available in 1080p"
        assert extract_quality(title, description) == "720p"

    def test_extract_quality_unknown(self):
        """Test returns 'Unknown' when no quality found."""
        title = "Anime - 01"
        assert extract_quality(title) == "Unknown"

    def test_extract_quality_case_insensitive(self):
        """Test case-insensitive matching."""
        assert extract_quality("Anime 1080P") == "1080P"
        assert extract_quality("Anime 4k") == "4k"


class TestExtractAudioLanguage:
    """Tests for audio language extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime English Dub", "English"),
            ("Anime Eng Dub", "English"),
            ("Anime [Dubbed]", "English"),
            ("Anime Dual Audio", "English"),
            ("Anime [DUAL]", "English"),
            ("Anime [Dub]", "English"),
        ],
    )
    def test_extract_audio_english(self, title, expected):
        """Test English audio language detection."""
        assert extract_audio_language(title, "", "") == expected

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime (Japanese)", "Japanese"),
            ("Anime [JPN]", "Japanese"),
            ("Anime Raw", "Japanese"),
            ("Anime [Jap]", "Japanese"),
        ],
    )
    def test_extract_audio_japanese(self, title, expected):
        """Test Japanese audio language detection."""
        assert extract_audio_language(title, "", "") == expected

    def test_extract_audio_from_description(self):
        """Test audio extraction from description."""
        assert extract_audio_language("Anime", "English Dub version", "") == "English"

    def test_extract_audio_from_category_raw(self):
        """Test Raw category sets Japanese audio."""
        assert extract_audio_language("Anime", "", "Anime - Raw") == "Japanese"

    def test_extract_audio_default_japanese(self):
        """Test default to Japanese for anime."""
        assert extract_audio_language("Anime Episode 01", "", "") == "Japanese"


class TestExtractSubtitleLanguage:
    """Tests for subtitle language extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime [English Sub]", "English"),
            ("Anime Eng Sub", "English"),
            ("Anime [Subbed]", "English"),
            ("Anime [Eng]", "English"),
        ],
    )
    def test_extract_subtitle_english(self, title, expected):
        """Test English subtitle detection."""
        assert extract_subtitle_language(title, "", "") == expected

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Anime Multi-Sub", "Multi"),
            ("Anime MultiSub", "Multi"),
            # Note: "Multi Sub" (space) doesn't match the regex pattern Multi-?Sub
        ],
    )
    def test_extract_subtitle_multi(self, title, expected):
        """Test multi-subtitle detection."""
        assert extract_subtitle_language(title, "", "") == expected

    def test_extract_subtitle_from_category_english(self):
        """Test English-translated category sets English subs."""
        result = extract_subtitle_language("Anime", "", "Anime - English-translated")
        assert result == "English"

    def test_extract_subtitle_from_category_raw(self):
        """Test Raw category sets None for subs."""
        result = extract_subtitle_language("Anime", "", "Anime - Raw")
        assert result == "None"

    def test_extract_subtitle_unknown(self):
        """Test returns Unknown when no match."""
        result = extract_subtitle_language("Anime 01", "", "")
        assert result == "Unknown"


class TestExtractAnimeName:
    """Tests for anime name extraction."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("[SubsPlease] Frieren - 01", "Frieren"),
            ("(Group) Spy x Family S02E01", "Spy x Family"),
            ("[Group] One Piece - 1050 [720p]", "One Piece"),
        ],
    )
    def test_extract_anime_name_clean(self, title, expected):
        """Test anime name extraction removes metadata."""
        result = extract_anime_name(title)
        assert expected in result or result == expected

    def test_extract_anime_name_removes_release_group(self):
        """Test that release group brackets are removed."""
        result = extract_anime_name("[SubsPlease] Frieren - 01")
        assert "SubsPlease" not in result
        assert "[" not in result

    def test_extract_anime_name_removes_episode_info(self):
        """Test that episode information is removed."""
        result = extract_anime_name("Anime Episode 01 (1080p)")
        assert "Episode" not in result
        assert "(1080p)" not in result

    def test_extract_anime_name_removes_season_info(self):
        """Test that season information is removed."""
        result = extract_anime_name("Anime S01E01")
        assert "S01" not in result

    def test_extract_anime_name_empty_returns_unknown(self):
        """Test returns Unknown for empty/whitespace input."""
        assert extract_anime_name("") == "Unknown"
        assert extract_anime_name("   ") == "Unknown"

    def test_extract_anime_name_only_brackets(self):
        """Test returns Unknown when only brackets present."""
        assert extract_anime_name("[Group]") == "Unknown"


@respx.mock
class TestFetchDetailPage:
    """Tests for fetching and parsing detail pages."""

    def test_fetch_detail_page_success(self, sample_detail_page_html):
        """Test successful detail page fetch."""
        torrent_id = "123456"

        respx.get(f"https://nyaa.si/view/{torrent_id}").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        with httpx.Client() as client:
            detail = fetch_detail_page(client, torrent_id)

        assert detail is not None
        assert "SubsPlease" in detail["title"]
        assert detail["submitter"] == "SubsPlease"
        assert "English-translated" in detail["category"]

    def test_fetch_detail_page_http_error(self, mock_console):
        """Test returns None on HTTP error."""
        torrent_id = "error"

        respx.get(f"https://nyaa.si/view/{torrent_id}").mock(
            return_value=httpx.Response(404)
        )

        with httpx.Client() as client:
            detail = fetch_detail_page(client, torrent_id)

        assert detail is None

    def test_fetch_detail_page_exception(self, mock_console):
        """Test returns None on network exception."""
        torrent_id = "exception"

        respx.get(f"https://nyaa.si/view/{torrent_id}").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with httpx.Client() as client:
            detail = fetch_detail_page(client, torrent_id)

        assert detail is None


class TestExtractMetadataFromDetail:
    """Tests for full metadata extraction."""

    def test_extract_metadata_complete(self):
        """Test complete metadata extraction."""
        detail = {
            "title": "[SubsPlease] Test Anime - 01 (1080p) [ABC].mkv",
            "submitter": "SubsPlease",
            "category": "Anime - English-translated",
            "description": "Season 1 Episode 1. English subtitles.",
        }

        metadata = extract_metadata_from_detail(detail)

        assert metadata.release_group == "SubsPlease"
        assert "Test Anime" in metadata.anime_name
        assert metadata.episode == "Episode 1"
        assert metadata.quality == "1080p"
        assert metadata.subtitle_language == "English"

    def test_extract_metadata_uses_submitter_as_group(self):
        """Test that submitter is used as release_group."""
        detail = {
            "title": "Anime Without Group - 01 (1080p)",
            "submitter": "TrustedUploader",
            "category": "",
            "description": "",
        }

        metadata = extract_metadata_from_detail(detail)
        assert metadata.release_group == "TrustedUploader"

    def test_extract_metadata_anonymous_submitter(self):
        """Test fallback when submitter is Anonymous."""
        detail = {
            "title": "[GroupName] Anime - 01",
            "submitter": "Anonymous",
            "category": "",
            "description": "",
        }

        metadata = extract_metadata_from_detail(detail)
        assert metadata.release_group == "GroupName"

    def test_extract_metadata_truncates_description(self):
        """Test description is truncated to 200 chars."""
        detail = {
            "title": "Anime - 01",
            "submitter": "Test",
            "category": "",
            "description": "A" * 500,
        }

        metadata = extract_metadata_from_detail(detail)
        assert len(metadata.description) == 200

    def test_extract_metadata_empty_description(self):
        """Test handles empty description."""
        detail = {
            "title": "Anime - 01",
            "submitter": "Test",
            "category": "",
            "description": "",
        }

        metadata = extract_metadata_from_detail(detail)
        assert metadata.description == ""


class TestPatterns:
    """Tests for regex pattern constants."""

    def test_patterns_dict_exists(self):
        """Test PATTERNS dictionary is populated."""
        assert len(PATTERNS) > 0

    def test_patterns_are_compiled(self):
        """Test all patterns are compiled regex objects."""
        import re

        for key, pattern in PATTERNS.items():
            assert isinstance(
                pattern, re.Pattern
            ), f"Pattern '{key}' is not compiled"

    def test_new_season_patterns_exist(self):
        """Test that new season patterns are defined."""
        expected_patterns = [
            "season_part",
            "season_cour",
            "season_ordinal_num",
            "season_ordinal_word",
            "season_roman",
        ]
        for pattern_name in expected_patterns:
            assert pattern_name in PATTERNS, f"Pattern '{pattern_name}' not found"


class TestSeasonHelperFunctions:
    """Tests for season extraction helper functions."""

    @pytest.mark.parametrize(
        "word,expected",
        [
            ("first", 1),
            ("second", 2),
            ("third", 3),
            ("fourth", 4),
            ("fifth", 5),
            ("sixth", 6),
            ("seventh", 7),
            ("eighth", 8),
            ("ninth", 9),
            ("tenth", 10),
            ("First", 1),  # Case insensitive
            ("SECOND", 2),
            ("Third", 3),
        ],
    )
    def test_parse_ordinal_word(self, word, expected):
        """Test ordinal word to integer conversion."""
        assert _parse_ordinal_word(word) == expected

    def test_parse_ordinal_word_unknown(self):
        """Test unknown ordinal word returns 1."""
        assert _parse_ordinal_word("eleventh") == 1
        assert _parse_ordinal_word("unknown") == 1

    @pytest.mark.parametrize(
        "numeral,expected",
        [
            ("I", 1),
            ("II", 2),
            ("III", 3),
            ("IV", 4),
            ("V", 5),
            ("VI", 6),
            ("VII", 7),
            ("VIII", 8),
            ("IX", 9),
            ("X", 10),
            ("i", 1),  # Case insensitive
            ("ii", 2),
            ("iii", 3),
            ("iv", 4),
        ],
    )
    def test_parse_roman_numeral(self, numeral, expected):
        """Test Roman numeral to integer conversion."""
        assert _parse_roman_numeral(numeral) == expected

    def test_parse_roman_numeral_empty(self):
        """Test empty/invalid Roman numeral returns 1."""
        assert _parse_roman_numeral("") == 1

    @pytest.mark.parametrize(
        "text,expected",
        [
            # Standard patterns
            ("S01", 1),
            ("S2", 2),
            ("Season 3", 3),
            ("Season 10", 10),
            # Ordinal numeric
            ("2nd Season", 2),
            ("3rd Season", 3),
            ("4th Season", 4),
            ("1st Season", 1),
            # Ordinal word
            ("Second Season", 2),
            ("Third Season", 3),
            ("First Season", 1),
            # Roman numeral
            ("Season II", 2),
            ("Season III", 3),
            ("Season IV", 4),
            # Part
            ("Part 1", 1),
            ("Part 2", 2),
            # Cour
            ("Cour 1", 1),
            ("Cour 2", 2),
        ],
    )
    def test_extract_season_number(self, text, expected):
        """Test season number extraction from various formats."""
        assert _extract_season_number(text) == expected

    def test_extract_season_number_no_match(self):
        """Test returns None when no season pattern found."""
        assert _extract_season_number("Just an anime title") is None
        assert _extract_season_number("No season here") is None


class TestExtractSeasonAdvanced:
    """Tests for advanced season extraction patterns."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            # Standard patterns (existing, should still work)
            ("Anime S01E01", "Season 1"),
            ("Anime S2 - 01", "Season 2"),
            ("Anime Season 3 Episode 01", "Season 3"),
            # Ordinal numeric: 2nd Season, 3rd Season
            ("[Group] Anime 2nd Season - 01", "Season 2"),
            ("My Hero Academia 3rd Season", "Season 3"),
            ("Attack on Titan 4th Season", "Season 4"),
            ("Anime 1st Season - 05", "Season 1"),
            # Ordinal word: Second Season, Third Season
            ("[SubsPlease] Anime Second Season - 01", "Season 2"),
            ("Sword Art Online Third Season", "Season 3"),
            ("Anime Fourth Season", "Season 4"),
            ("Anime First Season - 01", "Season 1"),
            # Roman numeral: Season II, Season III
            ("[Group] Anime Season II - 01", "Season 2"),
            ("Sword Art Online Season III", "Season 3"),
            ("Anime Season IV", "Season 4"),
            ("Anime Season I - 01", "Season 1"),
            # Part: Part 1, Part 2 (split-cour anime)
            ("Attack on Titan Final Season Part 2", "Season 2"),
            ("[Group] Anime Part 1 - 01", "Season 1"),
            ("Anime The Final Season Part 3", "Season 3"),
            # Cour: Cour 1, Cour 2
            ("[Group] Anime Cour 2 - 01", "Season 2"),
            ("Anime Final Season Cour 1", "Season 1"),
        ],
    )
    def test_extract_season_advanced_patterns(self, title, expected):
        """Test season extraction for advanced patterns."""
        assert extract_season(title) == expected

    def test_extract_season_from_description_advanced(self):
        """Test season extraction from description with advanced patterns."""
        title = "Anime - 01"
        # Ordinal word in description
        assert extract_season(title, "Second Season release") == "Season 2"
        # Roman numeral in description
        assert extract_season(title, "This is Season III") == "Season 3"

    def test_extract_season_priority_standard_first(self):
        """Test that standard patterns take priority."""
        # S01 should be found before Part 2
        title = "Anime S01 Part 2"
        assert extract_season(title) == "Season 1"

    def test_extract_season_case_insensitive(self):
        """Test case insensitivity for all patterns."""
        assert extract_season("Anime SECOND SEASON") == "Season 2"
        assert extract_season("Anime season ii") == "Season 2"
        assert extract_season("Anime PART 2") == "Season 2"
        assert extract_season("Anime cour 2") == "Season 2"
        assert extract_season("Anime 2ND SEASON") == "Season 2"


class TestExtractAnimeNameAdvanced:
    """Tests for anime name extraction with advanced season patterns."""

    @pytest.mark.parametrize(
        "title,expected_not_in",
        [
            # Ordinal patterns should be removed
            ("[Group] Anime 2nd Season - 01", "2nd Season"),
            ("[Group] Anime Second Season - 01", "Second Season"),
            ("[Group] Anime Third Season", "Third Season"),
            # Roman numeral should be removed
            ("[Group] Anime Season II - 01", "Season II"),
            ("[Group] Anime Season III", "Season III"),
            # Part should be removed
            ("[Group] Anime Part 2 - 01", "Part 2"),
            ("[Group] Attack on Titan Part 3", "Part 3"),
            # Cour should be removed
            ("[Group] Anime Cour 2 - 01", "Cour 2"),
        ],
    )
    def test_extract_anime_name_removes_advanced_seasons(self, title, expected_not_in):
        """Test that advanced season patterns are removed from anime names."""
        result = extract_anime_name(title)
        assert expected_not_in not in result

    def test_extract_anime_name_preserves_core_name(self):
        """Test that core anime name is preserved."""
        result = extract_anime_name("[SubsPlease] Attack on Titan 2nd Season - 01")
        assert "Attack" in result or "Titan" in result

        result = extract_anime_name("[Group] Sword Art Online Season III - 05")
        assert "Sword" in result or "Art" in result or "Online" in result
